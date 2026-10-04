"""Exercise the D1 API adapter using SQLite's actual prepared SQL semantics."""

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.cloudflare import app


class D1:
    def __init__(self, connection):
        self.connection = connection

    def prepare(self, sql):
        return Statement(self.connection, sql)


class Statement:
    def __init__(self, connection, sql):
        self.connection, self.sql, self.parameters = connection, sql, ()

    def bind(self, *parameters):
        self.parameters = parameters
        return self

    async def run(self):
        cursor = self.connection.execute(self.sql, self.parameters)
        results = [dict(row) for row in cursor.fetchall()]
        self.connection.commit()
        return {"success": True, "results": results}


@pytest.fixture
def client(tmp_path):
    connection = sqlite3.connect(tmp_path / "d1.db", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    migration = Path(__file__).parents[1] / "migrations/0001_cloudflare.sql"
    connection.executescript(migration.read_text())
    connection.executescript(migration.read_text())

    async def bound(scope, receive, send):
        scope["env"] = SimpleNamespace(DB=D1(connection))
        await app(scope, receive, send)

    with TestClient(bound) as client:
        yield client
    connection.close()


@pytest.mark.parametrize(
    "expression,angle,result",
    [
        ("(2+3)*4", "deg", "20"),
        ("2^3^2", "deg", "512"),
        ("-2^2", "deg", "-4"),
        ("2^-3", "deg", "0.125"),
        ("sin(30)", "deg", "0.5"),
        ("sin(pi/2)", "rad", "1"),
        ("0.1+0.2", "deg", "0.3"),
    ],
)
def test_calculation_and_steps(client, expression, angle, result):
    response = client.post(
        "/api/calculate", json={"expression": expression, "angle_mode": angle}
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["result"] == result
    assert data["steps"][-1]["after"] == result
    history = client.get("/api/history").json()["data"]
    assert history["items"][0]["angle_mode"] == angle
    assert history["total"] == 1


def test_history_search_pagination_delete(client):
    assert client.get("/api/health").json()["data"]["database"] == "connected"
    for expression in ("1+2", "4+5", "10%"):
        client.post("/api/calculate", json={"expression": expression})
    assert client.get("/api/history?q=%").json()["data"]["total"] == 1
    assert client.get("/api/history?q=' OR 1=1 --").json()["data"]["total"] == 0
    page = client.get("/api/history?page=2&page_size=1").json()["data"]
    assert page["total"] == 3
    assert len(page["items"]) == 1
    record_id = page["items"][0]["id"]
    assert client.delete(f"/api/history/{record_id}").status_code == 200
    assert client.delete(f"/api/history/{record_id}").status_code == 404


def test_invalid_calculation_does_not_save(client):
    response = client.post("/api/calculate", json={"expression": "1/0"})
    assert response.status_code == 400
    assert "position" in response.json()["error"]
    assert client.get("/api/history").json()["data"]["total"] == 0
    assert client.post("/api/calculate", json={"expression": 123}).status_code == 400


def test_formula_crud_conflict_and_history_independence(client):
    body = {"name": "倒数", "expression": "1/x", "parameter_labels": {"x": "数值"}}
    response = client.post("/api/formulas", json=body)
    assert response.status_code == 201
    item = response.json()["data"]
    url = f"/api/formulas/{item['id']}"
    assert item["parameter_labels"] == {"x": "数值"}
    assert len(client.get("/api/formulas").json()["data"]["items"]) == 5
    assert client.get("/api/formulas?q=倒数").json()["data"]["items"][0] == item
    failed = client.post(
        url + "/calculate",
        json={"parameters": {"x": "0"}, "updated_at": item["updated_at"]},
    )
    assert failed.status_code == 400
    assert client.get("/api/history").json()["data"]["total"] == 0
    success = client.post(
        url + "/calculate",
        json={"parameters": {"x": "-2"}, "updated_at": item["updated_at"]},
    )
    assert success.json()["data"]["result"] == "-0.5"
    revision = {**body, "updated_at": item["updated_at"], "name": "新倒数"}
    edited = client.put(url, json=revision).json()["data"]
    assert edited["updated_at"] != item["updated_at"]
    assert client.put(url, json=revision).status_code == 409
    assert (
        client.delete(url, params={"updated_at": item["updated_at"]}).status_code == 409
    )
    assert (
        client.delete(url, params={"updated_at": edited["updated_at"]}).status_code
        == 200
    )
    assert (
        client.post(
            url + "/calculate",
            json={"parameters": {"x": "2"}, "updated_at": edited["updated_at"]},
        ).status_code
        == 404
    )
    assert client.get("/api/history").json()["data"]["total"] == 1


def test_formula_parameter_errors_builtins_and_validation(client):
    assert client.post(
        "/api/formulas/validate", json={"expression": "sin(a)+pi+a^2"}
    ).json()["data"]["parameters"] == ["a"]
    cases = [
        ("circle-area", {"r": "1"}, "3.141592653589793238462643383"),
        ("circle-length", {"r": "1"}, "6.283185307179586476925286767"),
        ("hypotenuse", {"a": "3", "b": "4"}, "5"),
        ("quadratic", {"a": "2", "x": "-3", "b": "4", "c": "1"}, "7"),
    ]
    for key, parameters, expected in cases:
        response = client.post(
            f"/api/formulas/{key}/calculate", json={"parameters": parameters}
        )
        assert response.json()["data"]["result"] == expected
    failed = client.post(
        "/api/formulas/circle-area/calculate", json={"parameters": {"r": "sqrt(-1)"}}
    )
    assert failed.json()["error"]["parameter"] == "r"
    assert (
        client.post(
            "/api/formulas/circle-area/calculate", json={"parameters": {}}
        ).status_code
        == 400
    )
    assert client.delete("/api/formulas/circle-area?updated_at=x").status_code == 403


def test_database_failure_is_not_success():
    class BrokenD1:
        def prepare(self, sql):
            raise RuntimeError("private database details")

    async def bound(scope, receive, send):
        scope["env"] = SimpleNamespace(DB=BrokenD1())
        await app(scope, receive, send)

    with TestClient(bound) as client:
        response = client.post("/api/calculate", json={"expression": "1+2"})
        assert response.status_code == 503
        assert "private" not in response.text
