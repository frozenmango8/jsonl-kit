import gzip
import io
import sys

from jsonl_kit.reader import JsonlReader


def test_skips_blank_lines_and_reports_bad_ones(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"a": 1}\n\n   \nnot json\n{"a": 2}\n')
    reader = JsonlReader(str(path))
    assert list(reader) == [(1, {"a": 1}), (5, {"a": 2})]
    assert reader.skipped == 1
    err = capsys.readouterr().err
    assert f"{path}:4: invalid JSON at column 1:" in err


def test_bad_utf8_is_a_skipped_line(tmp_path, capsys):
    path = tmp_path / "bad.jsonl"
    path.write_bytes(b'{"a": 1}\n\xff\n{"a": 2}\n')
    reader = JsonlReader(str(path))
    assert [value for _, value in reader] == [{"a": 1}, {"a": 2}]
    assert reader.skipped == 1
    assert ":2: invalid utf-8" in capsys.readouterr().err


def test_crlf_and_no_trailing_newline(tmp_path):
    path = tmp_path / "crlf.jsonl"
    path.write_bytes(b'{"a": 1}\r\n{"a": 2}')
    reader = JsonlReader(str(path))
    assert [value for _, value in reader] == [{"a": 1}, {"a": 2}]


def test_strips_leading_bom(tmp_path):
    path = tmp_path / "bom.jsonl"
    path.write_bytes(b'\xef\xbb\xbf{"city": "M\xc3\xbcnchen"}\n')
    reader = JsonlReader(str(path))
    assert list(reader) == [(1, {"city": "München"})]
    assert reader.skipped == 0


def test_gzip_is_sniffed_without_relying_on_the_name(tmp_path):
    payload = b'{"n": 1}\n{"n": 2}\n'
    gz = tmp_path / "data.bin"
    with gzip.open(gz, "wb") as handle:
        handle.write(payload)
    plain_named_gz = tmp_path / "plain.jsonl.gz"
    plain_named_gz.write_bytes(payload)

    assert [v for _, v in JsonlReader(str(gz))] == [{"n": 1}, {"n": 2}]
    assert [v for _, v in JsonlReader(str(plain_named_gz))] == [{"n": 1}, {"n": 2}]


def test_gzip_bad_line_keeps_decompressed_line_numbers(tmp_path, capsys):
    raw = tmp_path / "logs.jsonl.gz"
    with gzip.open(raw, "wb") as handle:
        handle.write(b'{"ok": true}\nNOT\n{"ok": false}\n')
    reader = JsonlReader(str(raw))
    assert [v for _, v in reader] == [{"ok": True}, {"ok": False}]
    assert f"{raw}:2:" in capsys.readouterr().err


def test_stdin_and_dash(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b'{"a": 1}\n\n')))
    reader = JsonlReader("-")
    assert list(reader) == [(1, {"a": 1})]
    assert reader.name == "<stdin>"
    capsys.readouterr()


def test_gzip_stdin(monkeypatch):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(b'{"a": 1}\n{"a": 2}\n')
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(buf.getvalue())))
    assert [v for _, v in JsonlReader(None)] == [{"a": 1}, {"a": 2}]
