import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.main import create_app


@pytest.fixture
def database_url(tmp_path):
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def client(database_url):
    with TestClient(create_app(database_url)) as test_client:
        yield test_client


def test_calculation_persistence_and_actual_delete(database_url):
    with TestClient(create_app(database_url)) as first:
        response = first.post("/api/calculate", json={"expression": "0.1+0.2"})
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["result"] == "0.3"
        assert data["created_at"].endswith("+00:00")
    # Recreate the entire application with the same on-disk database.
    with TestClient(create_app(database_url)) as restarted:
        assert (
            restarted.get("/api/history").json()["data"]["items"][0]["id"] == data["id"]
        )
        assert restarted.delete(f"/api/history/{data['id']}").status_code == 200
        assert restarted.get("/api/history").json()["data"]["total"] == 0
        assert restarted.delete(f"/api/history/{data['id']}").status_code == 404
    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM calculation_history")) == 0
    engine.dispose()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"expression": 3},
        {"expression": None},
        {"expression": "1+2", "result": "3"},
        {"expression": "1/0"},
        {"expression": "1+"},
        {"expression": "x"},
        {"expression": ""},
    ],
)
def test_invalid_requests_do_not_write_history(client, body):
    response = client.post("/api/calculate", json=body)
    assert response.status_code == 400
    assert response.json()["success"] is False
    assert response.json()["error"]["message"]
    assert client.get("/api/history").json()["data"]["total"] == 0


def test_search_pagination_and_delete_selected_only(client):
    ids = []
    for expression in ["11+1", "22+2", "33+3"]:
        ids.append(
            client.post("/api/calculate", json={"expression": expression}).json()[
                "data"
            ]["id"]
        )
    first = client.get("/api/history?page_size=2").json()["data"]
    assert first["total"] == 3
    assert [item["id"] for item in first["items"]] == ids[:0:-1]
    second = client.get("/api/history?page=2&page_size=2").json()["data"]
    assert second["items"][0]["id"] == ids[0]
    assert client.get("/api/history?q=22").json()["data"]["total"] == 1
    assert client.get("/api/history?q=36").json()["data"]["total"] == 1
    assert client.get("/api/history?q=%25").json()["data"]["total"] == 0
    client.delete(f"/api/history/{ids[1]}")
    assert [
        item["id"] for item in client.get("/api/history").json()["data"]["items"]
    ] == [ids[2], ids[0]]


@pytest.mark.parametrize(
    "path",
    [
        "/api/history?page=0",
        "/api/history?page_size=101",
        "/api/history?page_size=0",
        "/api/history?page=x",
    ],
)
def test_invalid_paging(client, path):
    assert client.get(path).status_code == 400


def test_health_and_cors(client):
    assert client.get("/api/health").json()["data"]["database"] == "connected"
    response = client.options(
        "/api/calculate",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    other = client.get("/api/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in other.headers


def test_commit_failure_is_not_success(client, monkeypatch):
    def fail_commit(self):
        raise OperationalError("test", {}, Exception("simulated failure"))

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = client.post("/api/calculate", json={"expression": "2+3"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert client.get("/api/history").json()["data"]["total"] == 0


def test_trace_response_is_additive_and_history_stays_compatible(client):
    data = client.post("/api/calculate", json={"expression": "(2+3)*4"}).json()["data"]
    assert data["result"] == "20"
    assert data["steps"][0]["operation"] == "2 + 3"
    assert data["steps"][0]["before"] == "(2+3)*4"
    assert data["steps"][-1]["after"] == "20"
    assert isinstance(data["steps"][0]["highlight_start"], int)
    history = client.get("/api/history").json()["data"]["items"]
    assert history[0]["id"] == data["id"]
    assert "steps" not in history[0]


def test_small_result_preserves_all_digits_across_restart(database_url):
    expression = "-1.234567890123456789012345678E-1000"
    expected = "-0." + "0" * 999 + "1234567890123456789012345678"
    assert len(expected) > 1024
    with TestClient(create_app(database_url)) as client:
        response = client.post("/api/calculate", json={"expression": expression})
        assert response.status_code == 201
        record = response.json()["data"]
        assert record["result"] == expected
    with TestClient(create_app(database_url)) as client:
        saved = client.get("/api/history").json()["data"]["items"][0]
        assert saved["id"] == record["id"]
        assert saved["result"] == expected
