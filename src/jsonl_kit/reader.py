"""Read JSON Lines from a path or stdin."""

from __future__ import annotations

import gzip
import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, BinaryIO

_GZIP_MAGIC = b"\x1f\x8b"


class JsonlReader:
    """Yield ``(lineno, value)`` for each JSON value.

    Blank lines are skipped. A bad line increments ``skipped``, is reported
    on stderr as ``name:line: message``, and does not stop the scan.
    """

    def __init__(self, path: str | None) -> None:
        self.path = path
        self.name = "<stdin>"
        self.skipped = 0

    def __iter__(self) -> Iterator[tuple[int, Any]]:
        with _open_binary(self.path) as (raw, name):
            self.name = name
            if _peek(raw, 2) == _GZIP_MAGIC:
                gz = gzip.GzipFile(fileobj=raw)
                try:
                    yield from self._parse(gz)
                finally:
                    gz.close()
                return
            yield from self._parse(raw)

    def warn(self, lineno: int, message: str) -> None:
        self.skipped += 1
        print(f"{self.name}:{lineno}: {message}", file=sys.stderr, flush=True)

    def _parse(self, stream: BinaryIO | gzip.GzipFile) -> Iterator[tuple[int, Any]]:
        for lineno, raw_line in enumerate(stream, 1):
            try:
                text = raw_line.decode("utf-8")
            except UnicodeDecodeError:
                self.warn(lineno, "invalid utf-8")
                continue
            if lineno == 1:
                text = text.lstrip("\ufeff")
            text = text.rstrip("\r\n")
            if not text.strip():
                continue
            try:
                yield lineno, json.loads(text)
            except json.JSONDecodeError as exc:
                where = f"invalid JSON at column {exc.colno}: {exc.msg}"
                self.warn(lineno, where)


@contextmanager
def _open_binary(path: str | None) -> Iterator[tuple[BinaryIO, str]]:
    if path is None or path == "-":
        yield sys.stdin.buffer, "<stdin>"
        return
    with open(path, "rb") as handle:
        yield handle, path


def _peek(raw: BinaryIO, n: int) -> bytes:
    peek = getattr(raw, "peek", None)
    if peek is not None:
        return bytes(peek(n)[:n])
    pos = raw.tell()
    data = raw.read(n)
    raw.seek(pos)
    return data
