"""Command line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import deque
from typing import Any

from jsonl_kit import __version__
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
