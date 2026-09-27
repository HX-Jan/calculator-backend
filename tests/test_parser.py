from decimal import Decimal

import pytest

from app.errors import CalculatorError
from app.parser import calculate


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("12+8", "20"),
        ("8-13", "-5"),
        ("6*7", "42"),
        ("12/4", "3"),
        ("1+2*3", "7"),
        ("(1+2)*3", "9"),
        ("10/2+7", "12"),
        ("8-3*2", "2"),
        ("-5+8", "3"),
        ("3*-2", "-6"),
        ("0.1+0.2", "0.3"),
        (".5+1.", "1.5"),
        ("--2", "2"),
        ("1++2", "3"),
        ("1+-2", "-1"),
        ("-(2+3)", "-5"),
        ("((2+3)*(4-1))/5", "3"),
        ("8/4/2", "1"),
        ("8-4-2", "2"),
        ("2 × 3 ÷ 4", "1.5"),
        ("-0", "0"),
        ("42", "42"),
        ("1/3", "0.3333333333333333333333333333"),
        ("+2", "2"),
        ("2\n+\t3", "5"),
    ],
)
def test_valid_expressions(expression, expected):
    assert calculate(expression)[1] == expected


@pytest.mark.parametrize(
    "expression",
    [
        "",
        "  ",
        "1+",
        "()",
        "(1+2",
        "1+2)",
        "1 2",
        "2(3)",
        "2**3",
        "1//2",
        "1..2",
        "1,2",
        "a+1",
        "__import__('os')",
        "NaN",
        "Infinity",
        "1e3",
        "1/0",
        "0/0",
        "1/(2-2)",
        "9" * 29,
        "1" * 501,
        "(" * 33 + "1" + ")" * 33,
        "-" * 33 + "1",
        "[1]",
        "1;2",
        "2^3",
    ],
)
def test_invalid_expressions(expression):
    with pytest.raises(CalculatorError):
        calculate(expression)


def test_steps_follow_precedence():
    _, _, steps = calculate("1+2*3")
    assert steps == [
        {"operation": "2 * 3", "result": "6"},
        {"operation": "1 + 6", "result": "7"},
    ]


def test_numeric_range_limit():
    with pytest.raises(CalculatorError, match="范围"):
        calculate("*".join(["9" * 28] * 4))


def test_generated_integer_arithmetic():
    # Independent expected values, not a second implementation of the parser.
    for left in range(-8, 9):
        for right in range(-4, 5):
            assert Decimal(calculate(f"({left})+({right})*3")[1]) == left + right * 3
