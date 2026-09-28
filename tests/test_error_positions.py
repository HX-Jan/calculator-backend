import pytest
from fastapi.testclient import TestClient

from app.errors import CalculatorError
from app.main import create_app
from app.parser import calculate


@pytest.mark.parametrize(
    "expression,start,end,message",
    [
        ("2+*3", 2, 3, "数字"),
        ("sqrt(9", 6, 6, "右括号"),
        ("1+2)", 3, 4, "运算符"),
        (" π×*2", 3, 4, "数字"),
        ("1/(2-2)", 2, 7, "零"),
        ("asin(2)", 5, 6, "−1"),
        ("comb(3,4)", 7, 8, "不能大于"),
        ("logbase(8,1)", 10, 11, "底数"),
        ("  2+💥", 4, 6, "字符"),
        ("sin 30", 4, 6, "左括号"),
    ],
)
def test_source_positions(expression, start, end, message):
    with pytest.raises(CalculatorError) as error:
        calculate(expression)
    assert error.value.position == start
    assert error.value.end_position == end
    assert message in error.value.message


def test_error_contract_and_no_history(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path / 'position.db'}")) as client:
        response = client.post("/api/calculate", json={"expression": "2+*3"})
        error = response.json()["error"]
        assert response.status_code == 400
        assert error["position"] == 2 and error["end_position"] == 3
        assert client.get("/api/history").json()["data"]["total"] == 0
        assert (
            client.post("/api/calculate", json={"expression": "2+3"}).status_code == 201
        )
