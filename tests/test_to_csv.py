from jsonl_kit.cli import main


def test_to_csv_unions_keys_and_encodes_nested_values(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"status": 200, "user": {"country": "US"}, "ms": 12}',
                '{"status": 500, "msg": "nope, sorry"}',
                '{"ok": true, "note": null, "city": "München"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert main(["to-csv", str(path)]) == 0
    out, _ = capsys.readouterr()
    assert out == (
        "status,user,ms,msg,ok,note,city\n"
        '200,"{""country"": ""US""}",12,,,,\n'
        '500,,,"nope, sorry",,,\n'
        ",,,,true,,München\n"
    )


def test_to_csv_fields_stream_selected_columns(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    path.write_text('{"status": 200, "ms": 12}\n{"status": 500}\n', encoding="utf-8")
    assert main(["to-csv", "-f", "status, ms", str(path)]) == 0
    out, _ = capsys.readouterr()
    assert out == "status,ms\n200,12\n500,\n"


def test_to_csv_fields_header_on_empty_input(tmp_path, capsys):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    assert main(["to-csv", "--fields", "a,b", str(path)]) == 0
    out, _ = capsys.readouterr()
    assert out == "a,b\n"


def test_to_csv_skips_non_objects(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    path.write_text('1\n{"a": 1}\n', encoding="utf-8")
    assert main(["to-csv", str(path)]) == 1
    out, err = capsys.readouterr()
    assert out == "a\n1\n"
    assert "expected an object" in err
