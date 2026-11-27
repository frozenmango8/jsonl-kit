from jsonl_kit.cli import main


def _events(path, ids):
    path.write_text("".join(f'{{"id": "{item}"}}\n' for item in ids), encoding="utf-8")


def test_sample_is_deterministic_and_keeps_input_order(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    _events(path, list("abcdefg"))
    args = ["sample", "-n", "3", "--seed", "1", str(path)]
    assert main(args) == 0
    first, _ = capsys.readouterr()
    assert main(args) == 0
    second, _ = capsys.readouterr()
    assert first == second == '{"id": "d"}\n{"id": "f"}\n{"id": "g"}\n'


def test_sample_returns_the_file_when_n_is_larger(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    _events(path, ["a", "b"])
    assert main(["sample", "-n", "5", "--seed", "1", str(path)]) == 0
    out, _ = capsys.readouterr()
    assert out == '{"id": "a"}\n{"id": "b"}\n'


def test_sample_skips_bad_lines(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    path.write_text('{"id": "a"}\nbad\n{"id": "b"}\n', encoding="utf-8")
    assert main(["sample", "-n", "5", str(path)]) == 1
    out, err = capsys.readouterr()
    assert out == '{"id": "a"}\n{"id": "b"}\n'
    assert ":2:" in err


def test_sample_rejects_non_positive_n(capsys):
    assert main(["sample", "-n", "0"]) == 2
    _, err = capsys.readouterr()
    assert "-n must be at least 1" in err
