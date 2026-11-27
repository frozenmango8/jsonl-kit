from jsonl_kit.cli import main


def test_pick_paths_and_missing_fields(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"status": 200, "user": {"id": 7, "country": "US"}}\n{"status": 404}\n',
        encoding="utf-8",
    )
    assert main(["pick", "status,user.id", str(path)]) == 0
    out, _ = capsys.readouterr()
    assert out == '{"status": 200, "user.id": 7}\n{"status": 404, "user.id": null}\n'


def test_pick_index_and_bracket_key(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"items": ["a", "b"], "user": {"a,b": 1}, "status": 2}\n',
        encoding="utf-8",
    )
    assert main(["pick", 'items[-1],user["a,b"],status', str(path)]) == 0
    out, _ = capsys.readouterr()
    assert out == '{"items[-1]": "b", "user[\\"a,b\\"]": 1, "status": 2}\n'


def test_pick_rejects_an_empty_field(capsys):
    assert main(["pick", "status,,id"]) == 2
    _, err = capsys.readouterr()
    assert "empty field" in err
