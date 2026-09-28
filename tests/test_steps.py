import pytest

from app.parser import calculate


@pytest.mark.parametrize(
    "expression,result",
    [
        ("(2+3)*4", "20"),
        ("2+3*4", "14"),
        ("2^3^2", "512"),
        ("-2^2", "-4"),
        ("2^-3", "0.125"),
        ("(-2)^2", "4"),
        ("sqrt((2+7))*comb(5,2)", "30"),
        ("(2+3)*(2+3)", "25"),
        ("sin(30)+cos(60)", "1"),
        ("5!", "120"),
        ("  π * 0 ", "0"),
        ("0.1234567890123456789012345678+0", "0.1234567890123456789012345678"),
        ("42", "42"),
        ("e", "2.718281828459045235360287471"),
    ],
)
def test_trace_chain(expression, result):
    _, actual, steps = calculate(expression)
    assert actual == result
    assert steps[0]["before"] == expression
    assert steps[-1]["after"] == actual
    for i, step in enumerate(steps):
        assert step["label"]
        encoded = step["before"].encode("utf-16-le")
        a, b = step["highlight_start"] * 2, step["highlight_end"] * 2
        assert 0 <= a < b <= len(encoded)
        assert encoded[a:b].decode("utf-16-le")
        if i:
            assert steps[i - 1]["after"] == step["before"]


def test_precedence_and_duplicate_source_identity():
    _, _, steps = calculate("2^3^2")
    assert (
        steps[0]["before"][steps[0]["highlight_start"] : steps[0]["highlight_end"]]
        == "3^2"
    )
    assert steps[0]["after"] == "2^9"
    _, _, steps = calculate("(2+3)*(2+3)")
    assert steps[0]["after"] == "(5)*(2+3)"
    _, _, steps = calculate("(-2)^2")
    assert steps[-2]["after"] == "(-2)^2"


def test_angle_and_constant_rounding():
    _, result, steps = calculate("sin(pi/2)", "rad")
    assert result == "1"
    assert "RAD" in steps[-1]["label"]
    _, result, steps = calculate("pi")
    assert steps[0]["label"] == "读取常量"
    assert steps[-1]["label"] == "结果整理"
    assert steps[-1]["after"] == result
