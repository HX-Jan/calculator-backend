"""Run in CI or locally with an explicitly supplied disposable PostgreSQL DB."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

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
