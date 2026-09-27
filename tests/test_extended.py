from decimal import Decimal

import pytest

from app.errors import CalculatorError
from app.parser import calculate


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("asin(0.5)", "30"),
        ("acos(0.5)", "60"),
        ("atan(1)", "45"),
        ("sinh(0)", "0"),
        ("cosh(0)", "1"),
        ("tanh(0)", "0"),
        ("asinh(0)", "0"),
        ("acosh(1)", "0"),
        ("atanh(0)", "0"),
        ("abs(-3)", "3"),
        ("exp(0)", "1"),
        ("cbrt(-8)", "-2"),
        ("root(-32,5)", "-2"),
        ("logbase(8,2)", "3"),
        ("mod(-7,3)", "-1"),
        ("perm(5,2)", "20"),
        ("comb(5,2)", "10"),
        ("floor(-1.2)", "-2"),
        ("ceil(-1.2)", "-1"),
        ("1.2E-3", "0.0012"),
        ("1e3", "1000"),
        ("50%", "0.5"),
        ("200*10%", "20"),
        ("2^3!", "64"),
    ],
)
def test_extended(expression, expected):
    assert calculate(expression)[1] == expected


@pytest.mark.parametrize(
    "expression",
    [
        "asin(2)",
        "acos(-2)",
        "acosh(0)",
        "atanh(1)",
        "root(-4,2)",
        "root(1,0)",
        "root(0,-1)",
        "logbase(4,1)",
        "mod(1,0)",
        "perm(3,4)",
        "comb(1001,2)",
        "comb(3.5,2)",
        "comb(3)",
        "abs(1,2)",
        "1e",
        "1E10000000",
        "1E-10000000",
        "exp(3000)",
        "sinh(300)",
        "root(2,10001)",
    ],
)
def test_extended_domain(expression):
    with pytest.raises(CalculatorError):
        calculate(expression)


def test_inverse_unit():
    assert abs(
        Decimal(calculate("asin(1)", "rad")[1]) - Decimal("1.5707963267948966")
    ) < Decimal("1e-14")
    assert "[RAD]" in calculate("asin(1)", "rad")[2][-1]["operation"]
