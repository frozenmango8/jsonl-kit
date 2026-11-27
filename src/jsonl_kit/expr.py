"""Parse and evaluate filter expressions without calling eval."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

Node = tuple[Any, ...]

_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "\\": "\\",
    '"': '"',
    "'": "'",
}


class ExprError(Exception):
    pass


def compile_expr(source: str) -> Callable[[Any], bool]:
    node = _Parser(source).parse()

    def predicate(record: Any) -> bool:
        return bool(_eval(node, record))

    return predicate


def parse_path(source: str) -> tuple[str | int, ...]:
    parser = _Parser(source)
    parser._skip()
    if parser.i >= parser.n:
        raise ExprError("empty path")
    node = parser._primary()
    parser._skip()
    if parser.i != parser.n or node[0] != "path":
        raise ExprError(f"not a field path: {source.strip()!r}")
    return cast(tuple[str | int, ...], node[1])


def lookup(value: Any, parts: tuple[str | int, ...]) -> Any:
    current = value
    for part in parts:
        if isinstance(part, str):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
            continue
        if isinstance(current, list) and -len(current) <= part < len(current):
            current = current[part]
            continue
        return None
    return current


def _eval(node: Node, value: Any) -> Any:
    kind = node[0]
    if kind == "lit":
        return node[1]
    if kind == "list":
        return [_eval(item, value) for item in node[1]]
    if kind == "path":
        return lookup(value, node[1])
    if kind == "not":
        return not _eval(node[1], value)
    if kind == "and":
        left = bool(_eval(node[1], value))
        return left and bool(_eval(node[2], value))
    if kind == "or":
        left = bool(_eval(node[1], value))
        return left or bool(_eval(node[2], value))
    if kind == "cmp":
        return _cmp(str(node[1]), _eval(node[2], value), _eval(node[3], value))
    raise RuntimeError(f"unknown node {kind!r}")


def _cmp(op: str, left: Any, right: Any) -> bool:
    if op == "==":
        return bool(left == right)
    if op == "!=":
        return bool(left != right)
    if op == "in":
        return _contains(left, right)
    if op == "not in":
        return not _contains(left, right)
    if not _orderable(left, right):
        return False
    if op == "<":
        return bool(left < right)
    if op == "<=":
        return bool(left <= right)
    if op == ">":
        return bool(left > right)
    if op == ">=":
        return bool(left >= right)
    raise RuntimeError(f"unknown operator {op!r}")


def _contains(left: Any, right: Any) -> bool:
    if isinstance(right, list):
        return bool(left in right)
    if isinstance(right, str):
        return isinstance(left, str) and left in right
    return False


def _orderable(left: Any, right: Any) -> bool:
    # bool is a subclass of int; don't sort true/false against numbers.
    if isinstance(left, bool) or isinstance(right, bool):
        return False
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return True
    return isinstance(left, str) and isinstance(right, str)


class _Parser:
    def __init__(self, source: str) -> None:
        self.s = source
        self.n = len(source)
        self.i = 0

    def parse(self) -> Node:
        self._skip()
        if self.i >= self.n:
            raise ExprError("empty expression")
        node = self._or()
        self._skip()
        if self.i < self.n:
            raise ExprError(self._msg("unexpected input"))
        return node

    def _or(self) -> Node:
        left = self._and()
        while self._keyword("or"):
            left = ("or", left, self._and())
        return left

    def _and(self) -> Node:
        left = self._not()
        while self._keyword("and"):
            left = ("and", left, self._not())
        return left

    def _not(self) -> Node:
        if self._keyword("not"):
            return ("not", self._not())
        return self._cmp_expr()

    def _cmp_expr(self) -> Node:
        left = self._primary()
        op = self._cmp_op()
        if op is None:
            return left
        return ("cmp", op, left, self._primary())

    def _cmp_op(self) -> str | None:
        if self._keyword("not"):
            if not self._keyword("in"):
                raise ExprError(self._msg("expected 'in'"))
            return "not in"
        if self._keyword("in"):
            return "in"
        self._skip()
        for op in ("==", "!=", "<=", ">="):
            if self.s.startswith(op, self.i):
                self.i += 2
                return op
        if self.i < self.n and self.s[self.i] in "<>":
            op = self.s[self.i]
            self.i += 1
            return op
        return None

    def _primary(self) -> Node:
        self._skip()
        if self.i >= self.n:
            raise ExprError(self._msg("unexpected end of expression"))
        ch = self.s[self.i]
        if ch in "\"'":
            return ("lit", self._string())
        if ch == "-" or ch.isdigit():
            return ("lit", self._number())
        if ch == "(":
            return self._group()
        if ch == "[":
            return self._list()
        if ch.isalpha() or ch == "_":
            word = self._ident()
            if word in {"true", "True"}:
                return ("lit", True)
            if word in {"false", "False"}:
                return ("lit", False)
            if word in {"null", "None"}:
                return ("lit", None)
            if word in {"and", "or", "not", "in"}:
                raise ExprError(self._msg(f"unexpected {word}"))
            return self._path(word)
        raise ExprError(self._msg("unexpected character"))

    def _path(self, first: str) -> Node:
        parts: list[str | int] = [first]
        while True:
            self._skip()
            if self.i >= self.n:
                break
            if self.s[self.i] == ".":
                self.i += 1
                parts.append(self._ident())
                continue
            if self.s[self.i] == "[":
                self.i += 1
                self._skip()
                if self.i < self.n and self.s[self.i] in "\"'":
                    parts.append(self._string())
                else:
                    parts.append(self._index())
                self._expect("]")
                continue
            break
        return ("path", tuple(parts))

    def _group(self) -> Node:
        self._expect("(")
        self._skip()
        if self.i < self.n and self.s[self.i] == ")":
            self.i += 1
            return ("list", ())
        first = self._or()
        items = [first]
        comma = False
        while True:
            self._skip()
            if self.i < self.n and self.s[self.i] == ",":
                comma = True
                self.i += 1
                self._skip()
                if self.i < self.n and self.s[self.i] == ")":
                    break
                items.append(self._or())
                continue
            break
        self._expect(")")
        if comma:
            return ("list", tuple(items))
        return first

    def _list(self) -> Node:
        self._expect("[")
        items: list[Node] = []
        self._skip()
        if self.i < self.n and self.s[self.i] == "]":
            self.i += 1
            return ("list", tuple(items))
        while True:
            items.append(self._or())
            self._skip()
            if self.i < self.n and self.s[self.i] == ",":
                self.i += 1
                self._skip()
                if self.i < self.n and self.s[self.i] == "]":
                    break
                continue
            break
        self._expect("]")
        return ("list", tuple(items))

    def _index(self) -> int:
        self._skip()
        if self.i >= self.n:
            raise ExprError(self._msg("expected an index"))
        start = self.i
        if self.s[self.i] == "-":
            self.i += 1
        if self.i >= self.n or not self.s[self.i].isdigit():
            raise ExprError(self._msg("expected an index"))
        while self.i < self.n and self.s[self.i].isdigit():
            self.i += 1
        return int(self.s[start : self.i])

    def _number(self) -> int | float:
        start = self.i
        if self.s[self.i] == "-":
            self.i += 1
        if self.i >= self.n or not self.s[self.i].isdigit():
            raise ExprError(self._msg("expected a number"))
        while self.i < self.n and self.s[self.i].isdigit():
            self.i += 1
        if (
            self.i + 1 < self.n
            and self.s[self.i] == "."
            and self.s[self.i + 1].isdigit()
        ):
            self.i += 1
            while self.i < self.n and self.s[self.i].isdigit():
                self.i += 1
        if self.i < self.n and self.s[self.i] in "eE":
            end = self.i + 1
            if end < self.n and self.s[end] in "+-":
                end += 1
            exp = end
            while exp < self.n and self.s[exp].isdigit():
                exp += 1
            if exp == end:
                raise ExprError(self._msg("expected an exponent"))
            self.i = exp
        text = self.s[start : self.i]
        if any(ch in text for ch in ".eE"):
            return float(text)
        return int(text)

    def _string(self) -> str:
        quote = self.s[self.i]
        self.i += 1
        chars: list[str] = []
        while self.i < self.n:
            ch = self.s[self.i]
            if ch == quote:
                self.i += 1
                return "".join(chars)
            if ch == "\\":
                self.i += 1
                if self.i >= self.n or self.s[self.i] not in _ESCAPES:
                    raise ExprError(self._msg("bad string escape"))
                chars.append(_ESCAPES[self.s[self.i]])
                self.i += 1
                continue
            if ch == "\n":
                break
            chars.append(ch)
            self.i += 1
        raise ExprError(self._msg("unterminated string"))

    def _ident(self) -> str:
        self._skip()
        if self.i >= self.n or not (self.s[self.i].isalpha() or self.s[self.i] == "_"):
            raise ExprError(self._msg("expected a name"))
        start = self.i
        self.i += 1
        while self.i < self.n and (self.s[self.i].isalnum() or self.s[self.i] == "_"):
            self.i += 1
        return self.s[start : self.i]

    def _keyword(self, word: str) -> bool:
        self._skip()
        end = self.i + len(word)
        if self.s[self.i : end] != word:
            return False
        if end < self.n and (self.s[end].isalnum() or self.s[end] == "_"):
            return False
        self.i = end
        return True

    def _expect(self, token: str) -> None:
        self._skip()
        if not self.s.startswith(token, self.i):
            raise ExprError(self._msg(f"expected {token!r}"))
        self.i += len(token)

    def _skip(self) -> None:
        while self.i < self.n and self.s[self.i].isspace():
            self.i += 1

    def _msg(self, message: str) -> str:
        return f"{message} (at {self.i}: {self.s[self.i : self.i + 12]!r})"
