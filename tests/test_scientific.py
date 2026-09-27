from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.errors import CalculatorError
from app.main import create_app
from app.parser import calculate


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("sqrt(9)", "3"),
        ("2^3", "8"),
        ("2^-3", "0.125"),
        ("5!", "120"),
        ("0!", "1"),
        ("ln(e)", "1"),
        ("log(100)", "2"),
        ("2^3^2", "512"),
        ("-2^2", "-4"),
        ("(-2)^2", "4"),
        ("2^3!", "64"),
        ("sqrt(16)+3!", "10"),
        ("sin(30)", "0.5"),
        ("cos(60)", "0.5"),
        ("tan(45)", "1"),
        ("sin(180)", "0"),
        ("cos(90)", "0"),
        ("sin(-90)", "-1"),
        ("1/(2)", "0.5"),
        ("9^0.5", "3"),
        ("0.1+0.2", "0.3"),
    ],
)
def test_scientific_results(expression, expected):
    assert calculate(expression)[1] == expected


@pytest.mark.parametrize(
    "expression",
    [
        "sqrt(-1)",
        "ln(0)",
        "log(-2)",
        "(-1)!",
        "1.5!",
        "70!",
        "tan(90)",
        "tan(-90)",
        "0^-1",
        "0^0",
        "(-2)^0.5",
        "2pi",
        "sin 30",
        "sin()",
        "unknown(2)",
        "2^10001",
        "sin(1000000000001)",
        "sqrt(" * 34 + "1" + ")" * 34,
        "2^" * 34 + "1",
        "10^101",
    ],
)
def test_scientific_errors(expression):
    with pytest.raises(CalculatorError):
        calculate(expression)


def test_radians_and_steps():
    assert calculate("sin(pi/2)", "rad")[1] == "1"
    assert calculate("cos(π)", "rad")[1] == "-1"
    value = Decimal(calculate("sin(1)", "rad")[1])
    assert abs(value - Decimal("0.8414709848078965")) < Decimal("1e-14")
    assert "[RAD]" in calculate("sin(pi/2)", "rad")[2][-1]["operation"]
    with pytest.raises(CalculatorError):
        calculate("tan(pi/2)", "rad")


def test_scientific_api_and_persistence(tmp_path):
    url = f"sqlite:///{tmp_path / 'science.db'}"
    with TestClient(create_app(url)) as client:
        response = client.post(
            "/api/calculate", json={"expression": "sin(pi/2)", "angle_mode": "rad"}
        )
        assert response.status_code == 201
        assert response.json()["data"]["result"] == "1"
        assert response.json()["data"]["angle_mode"] == "rad"
        result = client.post("/api/calculate", json={"expression": "sin(30)"})
        assert result.json()["data"]["result"] == "0.5"
        for payload in [
            {"expression": "1", "angle_mode": "bad"},
            {"expression": "sqrt(-1)"},
            {"expression": "69!!"},
        ]:
            assert client.post("/api/calculate", json=payload).status_code == 400
        assert client.get("/api/history").json()["data"]["total"] == 2
    with TestClient(create_app(url)) as client:
        history = client.get("/api/history?q=pi").json()["data"]["items"]
        assert history[0]["angle_mode"] == "rad"
        assert client.delete(f"/api/history/{history[0]['id']}").status_code == 200


def test_legacy_database_upgrade_is_repeatable(tmp_path):
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE calculation_history (id INTEGER PRIMARY KEY, "
                "expression VARCHAR(500) NOT NULL, result VARCHAR(1024) NOT NULL, "
                "created_at DATETIME NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO calculation_history VALUES "
                "(1, '1+2', '3', '2026-09-27 00:00:00')"
            )
        )
    engine.dispose()
    for _ in range(2):
        with TestClient(create_app(url)) as client:
            record = client.get("/api/history").json()["data"]["items"][0]
            assert (record["id"], record["result"], record["angle_mode"]) == (
                1,
                "3",
                "deg",
            )
