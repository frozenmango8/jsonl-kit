import io
import sys

from jsonl_kit.cli import main


def _write(path, text):
    path.write_text(text, encoding="utf-8")


def test_head_and_tail_limits(tmp_path, capsys):
    path = tmp_path / "n.jsonl"
    _write(path, "".join(f'{{"i": {i}}}\n' for i in range(12)))

    assert main(["head", "-n", "2", str(path)]) == 0
    out, _ = capsys.readouterr()
    assert out == '{"i": 0}\n{"i": 1}\n'

    assert main(["tail", "-n", "2", str(path)]) == 0
    out, _ = capsys.readouterr()
    assert out == '{"i": 10}\n{"i": 11}\n'


def test_head_default_is_ten(tmp_path, capsys):
    path = tmp_path / "n.jsonl"
    _write(path, "".join(f'{{"i": {i}}}\n' for i in range(12)))
    assert main(["head", str(path)]) == 0
    out, _ = capsys.readouterr()
    assert out.count("\n") == 10
    assert out.startswith('{"i": 0}\n')
    assert '{"i": 9}\n' in out
    assert '{"i": 10}' not in out


def test_tail_shorter_than_n(tmp_path, capsys):
    path = tmp_path / "n.jsonl"
    _write(path, '{"i": 1}\n{"i": 2}\n')
    assert main(["tail", "-n", "5", str(path)]) == 0
    out, _ = capsys.readouterr()
    assert out == '{"i": 1}\n{"i": 2}\n'


def test_head_skips_a_bad_first_line(tmp_path, capsys):
    path = tmp_path / "n.jsonl"
    _write(path, 'nope\n{"i": 1}\n{"i": 2}\n')
    assert main(["head", "-n", "1", str(path)]) == 1
    out, err = capsys.readouterr()
    assert out == '{"i": 1}\n'
    assert ":1: invalid JSON" in err


def test_tail_reports_a_bad_line_in_the_middle(tmp_path, capsys):
    path = tmp_path / "n.jsonl"
    _write(path, '{"i": 1}\nbad\n{"i": 2}\n{"i": 3}\n')
    assert main(["tail", "-n", "2", str(path)]) == 1
    out, err = capsys.readouterr()
    assert out == '{"i": 2}\n{"i": 3}\n'
    assert ":2:" in err


def test_rejects_non_positive_n(capsys):
    assert main(["head", "-n", "0"]) == 2
    _, err = capsys.readouterr()
    assert "-n must be at least 1" in err


def test_missing_file(capsys):
    assert main(["head", "no-such.jsonl"]) == 2
    _, err = capsys.readouterr()
    assert err.startswith("jsonl:")
    assert "no-such.jsonl" in err


def test_stdin_unicode(monkeypatch, capsys):
    raw = '{"city": "München"}\n'.encode()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw)))
    assert main(["head", "-n", "1"]) == 0
    out, _ = capsys.readouterr()
    assert out == '{"city": "München"}\n'


def test_help_and_version(capsys):
    assert main(["--help"]) == 0
    out, _ = capsys.readouterr()
    assert "head" in out and "tail" in out
    assert main(["--version"]) == 0
    out, _ = capsys.readouterr()
    assert out.startswith("jsonl-kit 0.1.0")
