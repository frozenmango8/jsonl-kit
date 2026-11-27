# jsonl-kit

Small command-line tools for filtering, sampling and summarizing JSON Lines files.

[![ci](https://github.com/frozenmango8/jsonl-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/frozenmango8/jsonl-kit/actions/workflows/ci.yml)

## Install

```bash
pipx install jsonl-kit
```

From a checkout: `pipx install .`

## Usage

`FILE` is optional. Leave it off, or pass `-`, to read stdin. Gzip is detected from the magic bytes, including on stdin. Blank lines are ignored. Any other non-JSON line is written to stderr as `name:line: message` and skipped; the exit status is then 1.

The examples use this file:

```json
{"status": 200, "user": {"id": 1, "country": "US"}, "ms": 12}
{"status": 404, "user": {"id": 2, "country": "DE"}, "ms": 4}
{"status": 200, "user": {"id": 3, "country": "US"}, "ms": 30}
{"status": 500, "user": {"id": 4, "country": "US"}, "ms": 8}
```

```text
$ jsonl head -n 2 events.jsonl
{"status": 200, "user": {"id": 1, "country": "US"}, "ms": 12}
{"status": 404, "user": {"id": 2, "country": "DE"}, "ms": 4}

$ jsonl tail -n 1 events.jsonl
{"status": 500, "user": {"id": 4, "country": "US"}, "ms": 8}

$ jsonl filter 'status == 200 and user.country == "US"' events.jsonl
{"status": 200, "user": {"id": 1, "country": "US"}, "ms": 12}
{"status": 200, "user": {"id": 3, "country": "US"}, "ms": 30}

$ jsonl pick status,user.id events.jsonl
{"status": 200, "user.id": 1}
{"status": 404, "user.id": 2}
{"status": 200, "user.id": 3}
{"status": 500, "user.id": 4}

$ jsonl sample -n 2 --seed 1 events.jsonl
{"status": 404, "user": {"id": 2, "country": "DE"}, "ms": 4}
{"status": 500, "user": {"id": 4, "country": "US"}, "ms": 8}

$ jsonl stats events.jsonl
records: 4
skipped: 0

field         present  types   min  max
ms             100.0%  int       4   30
status         100.0%  int     200  500
user           100.0%  object
user.country   100.0%  str
user.id        100.0%  int       1    4

$ jsonl to-csv events.jsonl
status,user,ms
200,"{""id"": 1, ""country"": ""US""}",12
404,"{""id"": 2, ""country"": ""DE""}",4
200,"{""id"": 3, ""country"": ""US""}",30
500,"{""id"": 4, ""country"": ""US""}",8

$ printf '%s\n' '{"status": 200}' 'not json' '{"status": 201}' | jsonl head
{"status": 200}
<stdin>:2: invalid JSON at column 1: Expecting value
{"status": 201}
```

`head` and `tail` default to 10 records. `sample` prints in input order. `pick` uses the same paths as `filter` and writes null when a path is missing. `to-csv -f status,ms` selects columns; without `-f` every record is held until the header is known.

## Expressions

`filter` parses the expression itself. `eval` is not used.

`user.country` walks objects. `[0]` and `[-1]` index arrays, and `["odd-key"]` selects a key that is not an identifier. Comparisons are `== != < <= > >=`, `in`, and `not in`, combined with `and`, `or`, and `not`. Literals are `true`, `false`, `null` (or `True`, `False`, `None`) and quoted strings.

A missing path is null, so `user.country == "US"` is false when the field is absent, and `user.country == null` is true in that case too. `in` tests list membership, or a substring when the right-hand side is a string. Ordering a string against a number is false.

## Limitations

- One input, either a path or stdin. No multi-file walk.
- No arithmetic, function calls, or regular expressions in filters.
- `stats` records nested object keys (`user.country`) and stops at arrays. min/max are filled in for int and float values only.
- `to-csv` has one column per top-level key. Objects and arrays are JSON text. Null and missing both become an empty cell.
- `sample` keeps its reservoir in memory, and `tail` keeps the last N records. `to-csv` without `--fields` keeps every record. The other commands stream.
- Exit status is 1 when a line was skipped, and 2 for usage or expression errors.
