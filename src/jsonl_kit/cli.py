"""Command line interface."""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from collections import deque
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from jsonl_kit import __version__
from jsonl_kit.expr import ExprError, compile_expr, lookup, parse_path
from jsonl_kit.reader import JsonlReader


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jsonl",
        description="Streaming commands for JSON Lines.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"jsonl-kit {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    head = sub.add_parser("head", help="print the first N records")
    head.add_argument(
        "-n",
        type=int,
        default=10,
        metavar="N",
        help="how many records (default 10)",
    )
    _add_file(head)
    head.set_defaults(func=cmd_head)

    tail = sub.add_parser("tail", help="print the last N records")
    tail.add_argument(
        "-n",
        type=int,
        default=10,
        metavar="N",
        help="how many records (default 10)",
    )
    _add_file(tail)
    tail.set_defaults(func=cmd_tail)

    filt = sub.add_parser("filter", help="keep records matching an expression")
    filt.add_argument(
        "expr",
        metavar="EXPR",
        help='e.g. status == 200 and user.country == "US"',
    )
    _add_file(filt)
    filt.set_defaults(func=cmd_filter)

    pick = sub.add_parser("pick", help="keep selected fields")
    pick.add_argument(
        "fields",
        metavar="FIELDS",
        help="comma-separated paths, e.g. status,user.id",
    )
    _add_file(pick)
    pick.set_defaults(func=cmd_pick)

    sample = sub.add_parser("sample", help="reservoir-sample records")
    sample.add_argument("-n", type=int, required=True, metavar="N", help="sample size")
    sample.add_argument("--seed", type=int, default=None, help="RNG seed")
    _add_file(sample)
    sample.set_defaults(func=cmd_sample)

    stats = sub.add_parser("stats", help="per-key presence, types, and numeric range")
    _add_file(stats)
    stats.set_defaults(func=cmd_stats)

    to_csv = sub.add_parser("to-csv", help="write top-level keys as CSV")
    to_csv.add_argument(
        "-f",
        "--fields",
        help="column names; default is every key seen",
    )
    _add_file(to_csv)
    to_csv.set_defaults(func=cmd_to_csv)
    return parser


def _add_file(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "file",
        nargs="?",
        metavar="FILE",
        help="JSONL file; gzip is sniffed. Reads stdin if omitted",
    )


def _emit(value: Any) -> None:
    json.dump(value, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def _check_n(n: int) -> str | None:
    if n < 1:
        return "-n must be at least 1"
    return None


def _status(reader: JsonlReader) -> int:
    return 1 if reader.skipped else 0


def cmd_head(args: argparse.Namespace) -> int:
    message = _check_n(args.n)
    if message:
        print(f"jsonl: {message}", file=sys.stderr)
        return 2
    reader = JsonlReader(args.file)
    seen = 0
    for _, value in reader:
        _emit(value)
        seen += 1
        if seen >= args.n:
            break
    return _status(reader)


def cmd_tail(args: argparse.Namespace) -> int:
    message = _check_n(args.n)
    if message:
        print(f"jsonl: {message}", file=sys.stderr)
        return 2
    reader = JsonlReader(args.file)
    last: deque[Any] = deque(maxlen=args.n)
    for _, value in reader:
        last.append(value)
    for value in last:
        _emit(value)
    return _status(reader)


def _split_fields(spec: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in spec:
        if ch == "[":
            depth += 1
        elif ch == "]" and depth:
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    parts.append("".join(buf).strip())
    if any(part == "" for part in parts):
        raise ExprError("empty field in list")
    return parts


def cmd_pick(args: argparse.Namespace) -> int:
    try:
        fields = [(name, parse_path(name)) for name in _split_fields(args.fields)]
    except ExprError as exc:
        print(f"jsonl: {exc}", file=sys.stderr)
        return 2
    reader = JsonlReader(args.file)
    for _, value in reader:
        _emit({name: lookup(value, parts) for name, parts in fields})
    return _status(reader)


def cmd_sample(args: argparse.Namespace) -> int:
    message = _check_n(args.n)
    if message:
        print(f"jsonl: {message}", file=sys.stderr)
        return 2
    rng = random.Random(args.seed)
    reader = JsonlReader(args.file)
    # Algorithm R. Keep the original index so the sample stays in input order.
    chosen: list[tuple[int, Any]] = []
    for index, (_, value) in enumerate(reader):
        if index < args.n:
            chosen.append((index, value))
            continue
        slot = rng.randrange(index + 1)
        if slot < args.n:
            chosen[slot] = (index, value)
    chosen.sort()
    for _, value in chosen:
        _emit(value)
    return _status(reader)


_TYPE_ORDER = ("null", "bool", "int", "float", "str", "array", "object")


@dataclass
class _Col:
    count: int = 0
    types: set[str] = field(default_factory=set)
    low: int | float | None = None
    high: int | float | None = None

    def add_number(self, number: int | float) -> None:
        if self.low is None or number < self.low:
            self.low = number
        if self.high is None or number > self.high:
            self.high = number


def _typename(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "other"


def _walk(cols: dict[str, _Col], obj: dict[str, Any], prefix: str) -> None:
    for key, value in obj.items():
        path = f"{prefix}.{key}" if prefix else key
        col = cols.get(path)
        if col is None:
            col = cols[path] = _Col()
        col.count += 1
        col.types.add(_typename(value))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            col.add_number(value)
        if isinstance(value, dict):
            _walk(cols, value, path)


def _render_stats(records: int, skipped: int, cols: dict[str, _Col]) -> str:
    lines = [f"records: {records}", f"skipped: {skipped}"]
    if records == 0 or not cols:
        return "\n".join(lines) + "\n"
    ranked = sorted(cols.items(), key=lambda item: (-item[1].count, item[0]))
    rows: list[tuple[str, str, str, str, str]] = []
    for name, col in ranked:
        pct = 100.0 * col.count / records
        types = ", ".join(kind for kind in _TYPE_ORDER if kind in col.types)
        rows.append((name, f"{pct:.1f}%", types, _num(col.low), _num(col.high)))
    header = ("field", "present", "types", "min", "max")
    widths = [len(cell) for cell in header]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def fmt(row: tuple[str, str, str, str, str]) -> str:
        field_name, present, types, low, high = row
        text = (
            f"{field_name:<{widths[0]}}  {present:>{widths[1]}}  "
            f"{types:<{widths[2]}}  {low:>{widths[3]}}  {high:>{widths[4]}}"
        )
        return text.rstrip()

    lines.append("")
    lines.append(fmt(header))
    lines.extend(fmt(row) for row in rows)
    return "\n".join(lines) + "\n"


def _num(value: int | float | None) -> str:
    if value is None:
        return ""
    return json.dumps(value)


def cmd_stats(args: argparse.Namespace) -> int:
    reader = JsonlReader(args.file)
    cols: dict[str, _Col] = {}
    records = 0
    for _, value in reader:
        records += 1
        if isinstance(value, dict):
            _walk(cols, value, "")
    sys.stdout.write(_render_stats(records, reader.skipped, cols))
    return _status(reader)


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _write_csv(columns: list[str], rows: Iterable[Mapping[str, Any]]) -> None:
    # Pin the line ending so Windows doesn't rewrite the stream as CRLF.
    writer = csv.writer(sys.stdout, lineterminator="\n")
    if not columns:
        return
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_csv_cell(row.get(key)) for key in columns])


def _objects(reader: JsonlReader) -> Iterator[dict[str, Any]]:
    for lineno, value in reader:
        if isinstance(value, dict):
            yield value
            continue
        reader.warn(lineno, "expected an object")


def cmd_to_csv(args: argparse.Namespace) -> int:
    try:
        columns = _split_fields(args.fields) if args.fields else None
    except ExprError as exc:
        print(f"jsonl: {exc}", file=sys.stderr)
        return 2
    reader = JsonlReader(args.file)
    if columns is not None:
        _write_csv(columns, _objects(reader))
        return _status(reader)
    seen: dict[str, None] = {}
    rows: list[dict[str, Any]] = []
    for row in _objects(reader):
        rows.append(row)
        for key in row:
            if key not in seen:
                seen[key] = None
    _write_csv(list(seen), rows)
    return _status(reader)


def cmd_filter(args: argparse.Namespace) -> int:
    try:
        predicate = compile_expr(args.expr)
    except ExprError as exc:
        print(f"jsonl: {exc}", file=sys.stderr)
        return 2
    reader = JsonlReader(args.file)
    for _, value in reader:
        if predicate(value):
            _emit(value)
    return _status(reader)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 2
    try:
        return int(args.func(args))
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        return 130
    except OSError as exc:
        print(f"jsonl: {exc}", file=sys.stderr)
        return 2


def console_main() -> None:
    try:
        code = main()
    except BrokenPipeError:
        _drop_stdout()
        raise SystemExit(0) from None
    try:
        sys.stdout.flush()
    except BrokenPipeError:
        _drop_stdout()
        raise SystemExit(0) from None
    raise SystemExit(code)


def _drop_stdout() -> None:
    # Python flushes stdout again at shutdown and would report a second EPIPE.
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
    except OSError:
        return
    try:
        os.dup2(devnull, sys.stdout.fileno())
    except OSError:
        pass
    finally:
        os.close(devnull)
