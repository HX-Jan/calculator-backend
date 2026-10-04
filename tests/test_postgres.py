"""Run in CI or locally with an explicitly supplied disposable PostgreSQL DB."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine, inspect, text

from app.database import initialize_database
from app.main import create_app


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="No test PostgreSQL URL")
def test_postgres_persistence_contract():
    url = os.environ["TEST_POSTGRES_URL"]
    # Unique valid number; do not remove other records in a shared test database.
    expression = str(int(uuid4().hex[:12], 16)) + "+0.1"
    with TestClient(create_app(url)) as client:
        response = client.post("/api/calculate", json={"expression": expression})
        assert response.status_code == 201
        record = response.json()["data"]
    with TestClient(create_app(url)) as restarted:
        try:
            matches = restarted.get("/api/history", params={"q": expression}).json()[
                "data"
            ]
            assert matches["items"][0]["result"] == record["result"]
        finally:
            assert restarted.delete(f"/api/history/{record['id']}").status_code == 200
        assert (
            restarted.get("/api/history", params={"q": expression}).json()["data"][
                "total"
            ]
            == 0
        )


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="No test PostgreSQL URL")
def test_postgres_formula_persistence_and_revision():
    url = os.environ["TEST_POSTGRES_URL"]
    with TestClient(create_app(url)) as client:
        response = client.post(
            "/api/formulas",
            json={"name": "测试" + uuid4().hex[:12], "expression": "x+1"},
        )
        assert response.status_code == 201
        item = response.json()["data"]
    with TestClient(create_app(url)) as client:
        try:
            changed = client.put(
                f"/api/formulas/{item['id']}",
                json={
                    "name": item["name"],
                    "expression": "x+2",
                    "updated_at": item["updated_at"],
                },
            )
            assert changed.status_code == 200
            updated = changed.json()["data"]
            assert updated["expression"] == "x+2"
            assert (
                client.put(
                    f"/api/formulas/{item['id']}",
                    json={
                        "name": item["name"],
                        "expression": "x",
                        "updated_at": item["updated_at"],
                    },
                ).status_code
                == 409
            )
            item = updated
        finally:
            assert (
                client.delete(
                    f"/api/formulas/{item['id']}",
                    params={"updated_at": item["updated_at"]},
                ).status_code
                == 200
            )


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="No test PostgreSQL URL")
def test_postgres_legacy_result_column_upgrade_preserves_long_results():
    url = os.environ["TEST_POSTGRES_URL"].replace(
        "postgresql://", "postgresql+psycopg://", 1
    )
    schema = "audit_" + uuid4().hex
    admin = create_engine(url)
    # An isolated schema exercises legacy DDL without changing shared test tables.
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    expression = "-1.234567890123456789012345678E-1000"
    expected = "-0." + "0" * 999 + "1234567890123456789012345678"
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE calculation_history (id INTEGER PRIMARY KEY, "
                    "expression VARCHAR(500) NOT NULL, result VARCHAR(1024) NOT NULL, "
                    "created_at TIMESTAMPTZ NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO calculation_history VALUES "
                    "(1, '1+2', '3', CURRENT_TIMESTAMP)"
                )
            )
        for _ in range(2):
            initialize_database(engine)
        result_type = next(
            c["type"]
            for c in inspect(engine).get_columns("calculation_history")
            if c["name"] == "result"
        )
        assert isinstance(result_type, String) and result_type.length is None
        with engine.begin() as connection:
            assert (
                connection.scalar(
                    text("SELECT result FROM calculation_history WHERE id=1")
                )
                == "3"
            )
            assert (
                connection.scalar(
                    text("SELECT angle_mode FROM calculation_history WHERE id=1")
                )
                == "deg"
            )
            connection.execute(
                text(
                    "INSERT INTO calculation_history "
                    "(id,expression,result,created_at) "
                    "VALUES (2,:expression,:result,CURRENT_TIMESTAMP)"
                ),
                {"expression": expression, "result": expected},
            )
            assert (
                connection.scalar(
                    text("SELECT result FROM calculation_history WHERE id=2")
                )
                == expected
            )
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
