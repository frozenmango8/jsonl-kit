import pytest

from jsonl_kit.expr import ExprError, compile_expr, parse_path

_US = {"status": 200, "user": {"country": "US", "id": 1}}


@pytest.mark.parametrize(
    ("expr", "record", "expected"),
    [
        ('status == 200 and user.country == "US"', _US, True),
        (
            'status == 200 and user.country == "US"',
            {"status": 200, "user": {"country": "DE"}},
            False,
        ),
        (
            'status == 200 and user.country == "US"',
            {"status": 404, "user": {"country": "US"}},
            False,
        ),
        ('status == 200 and user.country == "US"', {"status": 200}, False),
        ("  status==200  and  user.country=='US'  ", _US, True),
        ("status != 200", {"status": 404}, True),
        ("n > 1 and n <= 3", {"n": 3}, True),
        ("n >= 1.5", {"n": 1.5}, True),
        ("n == -1.5", {"n": -1.5}, True),
        ("n == 1e2", {"n": 100}, True),
        ("name > 1", {"name": "abc"}, False),
        ("name > 1", {"name": 2}, True),
        ('country >= "US"', {"country": "US"}, True),
        ('country > "US"', {"country": "US"}, False),
        ("ok == true", {"ok": True}, True),
        ("ok == false", {"ok": False}, True),
        ("note == null", {"note": None}, True),
        ("note == None", {}, True),
        ("status in [200, 201]", {"status": 201}, True),
        ("status in (200, 201)", {"status": 200}, True),
        ("status in [200,]", {"status": 200}, True),
        ("status not in [404, 500]", {"status": 200}, True),
        ("code in allow", {"code": "A", "allow": ["A", "B"]}, True),
        ('"err" in message', {"message": "upstream err"}, True),
        ("1 in name", {"name": "abc"}, False),
        ("false or true and false", {}, False),
        ("true or false and false", {}, True),
        ("not true or true", {}, True),
        ("not (true or true)", {}, False),
        (
            "(status == 200 or status == 201) and country == 'US'",
            {"status": 201, "country": "US"},
            True,
        ),
        (
            "(status == 200 or status == 201) and country == 'US'",
            {"status": 201, "country": "DE"},
            False,
        ),
        ("ok", {"ok": True}, True),
        ("ok", {"ok": False}, False),
        ("name", {}, False),
        ("items[-1].id == 2", {"items": [{"id": 1}, {"id": 2}]}, True),
        ('user["country"] == "US"', _US, True),
        (r"'a\nb' == name", {"name": "a\nb"}, True),
        ("tags == ['a', 'b']", {"tags": ["a", "b"]}, True),
        ("missing == null", {"missing": None}, True),
    ],
)
def test_expressions(expr, record, expected):
    assert compile_expr(expr)(record) is expected


@pytest.mark.parametrize(
    "expr",
    [
        "",
        "   ",
        "status = 1",
        '__import__("os").system("echo pwned")',
        "status == ",
        "'unterminated",
        r"'bad \u00e9'",
        "user.",
        "status not 1",
        "and true",
    ],
)
def test_rejected_expressions(expr):
    with pytest.raises(ExprError):
        compile_expr(expr)


def test_parse_path():
    assert parse_path("user.id") == ("user", "id")
    assert parse_path("items[-1].id") == ("items", -1, "id")
    assert parse_path('user["first-name"]') == ("user", "first-name")
    with pytest.raises(ExprError):
        parse_path("a == 1")
    with pytest.raises(ExprError):
        parse_path("")
