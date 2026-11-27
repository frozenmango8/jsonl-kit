from jsonl_kit.cli import main


def test_filter_keeps_matches_and_reports_bad_lines(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"status": 200, "user": {"country": "US"}}',
                '{"status": 200, "user": {"country": "DE"}}',
                '{"status": 404, "user": {"country": "US"}}',
                "nope",
                '{"status": 200, "user": {"id": 4, "country": "US"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    code = main(["filter", 'status == 200 and user.country == "US"', str(path)])
    assert code == 1
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        '{"status": 200, "user": {"country": "US"}}',
        '{"status": 200, "user": {"id": 4, "country": "US"}}',
    ]
    assert ":4:" in err


def test_bad_expression_exits_before_opening_the_file(capsys):
    assert main(["filter", "???", "missing.jsonl"]) == 2
    _, err = capsys.readouterr()
    assert err.startswith("jsonl:")
    assert "missing.jsonl" not in err
