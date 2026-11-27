from jsonl_kit.cli import main

_TABLE = """\
records: 3
skipped: 0

field         present  types       min  max
status         100.0%  int         200  404
ms              66.7%  int, float  1.5    2
ok              66.7%  bool
user            66.7%  object
user.country    66.7%  str
note            33.3%  null
"""


def test_stats_table(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"status": 200, "user": {"country": "US"}, "ok": true, "ms": 1.5}',
                '{"status": 404, "user": {"country": "DE"}, "ok": false, "ms": 2}',
                '{"status": 200, "note": null}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert main(["stats", str(path)]) == 0
    out, _ = capsys.readouterr()
    assert out == _TABLE


def test_stats_empty_and_bad_lines(tmp_path, capsys):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert main(["stats", str(empty)]) == 0
    out, _ = capsys.readouterr()
    assert out == "records: 0\nskipped: 0\n"

    bad = tmp_path / "bad.jsonl"
    bad.write_text("nope\n", encoding="utf-8")
    assert main(["stats", str(bad)]) == 1
    out, err = capsys.readouterr()
    assert out == "records: 0\nskipped: 1\n"
    assert ":1:" in err


def test_stats_does_not_walk_into_arrays(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    path.write_text('{"items": [{"id": 1}], "n": 3}\n1\n', encoding="utf-8")
    assert main(["stats", str(path)]) == 0
    out, _ = capsys.readouterr()
    assert "records: 2" in out
    assert "50.0%" in out
    assert "array" in out
    assert "items.id" not in out
