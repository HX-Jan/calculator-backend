import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path / 'formulas.db'}")) as client:
        yield client


def create(client, expression="1/x", **extra):
    response = client.post(
        "/api/formulas", json={"name": "测试公式", "expression": expression, **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def compute(client, item, parameters, angle="deg"):
    return client.post(
        f"/api/formulas/{item['id']}/calculate",
        json={
            "parameters": parameters,
            "angle_mode": angle,
            "updated_at": item["updated_at"],
        },
    )


def test_builtin_examples_and_readonly(client):
    items = client.get("/api/formulas").json()["data"]["items"]
    assert len(items) == 4
    cases = [
        ({"r": "1"}, "3.141592653589793238462643383"),
        ({"r": "1"}, "6.283185307179586476925286767"),
        ({"a": "3", "b": "4"}, "5"),
        ({"a": "2", "x": "-3", "b": "4", "c": "1"}, "7"),
    ]
    for item, (parameters, expected) in zip(items, cases, strict=True):
        response = compute(client, item, parameters)
        assert response.status_code == 201, response.text
        assert response.json()["data"]["result"] == expected
        assert (
            client.put(
                f"/api/formulas/{item['id']}", json={"name": "改名", "expression": "x"}
            ).status_code
            == 403
        )
        assert (
            client.delete(
                f"/api/formulas/{item['id']}", params={"updated_at": "x"}
            ).status_code
            == 403
        )
    assert len(client.get("/api/formulas?q=圆").json()["data"]["items"]) == 2


@pytest.mark.parametrize(
    "expression,parameters",
    [
        ("1/x", ["x"]),
        ("sqrt(-1)+x!", ["x"]),
        ("sin(x)+pi+e+1E-3", ["x"]),
        ("a*x^2+b*x+c", ["a", "x", "b", "c"]),
        ("root(x,n)+comb(n,r)", ["x", "n", "r"]),
        ("2^-x", ["x"]),
        ("2^3^x", ["x"]),
        ("42", []),
        ("π*r^2", ["r"]),
    ],
)
def test_validate_without_evaluation(client, expression, parameters):
    response = client.post("/api/formulas/validate", json={"expression": expression})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["parameters"] == parameters


@pytest.mark.parametrize(
    "expression",
    [
        "ab+1",
        "X+1",
        "2x",
        "sin(x,y)",
        "sqrt()",
        "x(",
        "a+b+c+d+f+g+h+i+j",
        "x+",
        "x" * 501,
        "(" * 34 + "x" + ")" * 34,
        "__import__(x)",
        "sin",
        "1.2.3",
    ],
)
def test_invalid_syntax(client, expression):
    assert (
        client.post(
            "/api/formulas/validate", json={"expression": expression}
        ).status_code
        == 400
    )


def test_domain_errors_and_parameter_errors_do_not_save(client):
    item = create(client)
    response = compute(client, item, {"x": "0"})
    assert response.status_code == 400
    assert "parameter" not in response.json()["error"]
    for value in ["sqrt(-1)", "y+1", "", "1/0"]:
        response = compute(client, item, {"x": value})
        assert response.status_code == 400
        assert response.json()["error"]["parameter"] == "x"
    for parameters in [{}, {"x": "2", "z": "3"}]:
        assert compute(client, item, parameters).status_code == 400
    assert client.get("/api/history").json()["data"]["total"] == 0
    response = compute(client, item, {"x": "1/3"})
    assert response.json()["data"]["result"] == "3"


def test_negative_repeated_parameters_angle_and_precision(client):
    item = create(client, "x^2+x", parameter_labels={"x": "输入值"})
    response = compute(client, item, {"x": "-3"}).json()["data"]
    assert response["result"] == "6"
    assert response["expression"] == "(-3)^2+(-3)"
    assert response["steps"][-1]["after"] == "6"
    item = create(client, "sin(x)")
    assert compute(client, item, {"x": "pi/2"}, "rad").json()["data"]["result"] == "1"
    item = create(client, "x+0")
    assert (
        compute(client, item, {"x": "0.1234567890123456789012345678"}).json()["data"][
            "result"
        ]
        == "0.1234567890123456789012345678"
    )


def test_edit_conflict_delete_and_history_independence(client):
    item = create(client, "x+1")
    response = client.put(
        f"/api/formulas/{item['id']}",
        json={"name": "更新", "expression": "x+2", "updated_at": item["updated_at"]},
    )
    assert response.status_code == 200, response.text
    changed = response.json()["data"]
    assert changed["updated_at"] != item["updated_at"]
    assert changed["expression"] == "x+2"
    assert compute(client, item, {"x": "2"}).status_code == 409
    assert (
        client.put(
            f"/api/formulas/{item['id']}",
            json={"name": "冲突", "expression": "x", "updated_at": item["updated_at"]},
        ).status_code
        == 409
    )
    assert (
        client.delete(
            f"/api/formulas/{item['id']}", params={"updated_at": item["updated_at"]}
        ).status_code
        == 409
    )
    calculated = compute(client, changed, {"x": "2"}).json()["data"]
    assert (
        client.delete(
            f"/api/formulas/{item['id']}", params={"updated_at": changed["updated_at"]}
        ).status_code
        == 200
    )
    assert compute(client, changed, {"x": "2"}).status_code == 404
    assert (
        client.post(
            "/api/calculate", json={"expression": calculated["expression"]}
        ).json()["data"]["result"]
        == "4"
    )


def test_expansion_limits_and_labels(client):
    item = create(client, "+".join(["x"] * 100))
    assert compute(client, item, {"x": "1+2+3"}).status_code == 400
    for extra in [
        {"name": " "},
        {"name": "字" * 41},
        {"parameter_labels": {"z": "错误"}},
        {"parameter_labels": {"x": "字" * 41}},
    ]:
        assert (
            client.post(
                "/api/formulas", json={"name": "例子", "expression": "x", **extra}
            ).status_code
            == 400
        )


def test_persistence_shared_clients_and_additive_upgrade(tmp_path):
    path = tmp_path / "legacy.db"
    url = f"sqlite:///{path}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE calculation_history (id INTEGER PRIMARY KEY, "
            "expression VARCHAR(500), result VARCHAR(1024), created_at DATETIME)"
        )
        connection.exec_driver_sql(
            "INSERT INTO calculation_history VALUES "
            "(1, '1+1', '2', '2026-09-28 00:00:00')"
        )
    with TestClient(create_app(url)) as first:
        item = create(first, "x+1")
        with TestClient(create_app(url)) as second:
            assert any(
                row["id"] == item["id"]
                for row in second.get("/api/formulas").json()["data"]["items"]
            )
    with TestClient(create_app(url)) as restarted:
        assert len(restarted.get("/api/formulas").json()["data"]["items"]) == 5
        assert restarted.get("/api/history").json()["data"]["total"] == 1
    assert "formulas" in inspect(engine).get_table_names()
    engine.dispose()


@pytest.mark.parametrize(
    "expression",
    ["1e999999999999999999999999999999", "1e101", "12345678901234567890123456789"],
)
def test_literal_limits_return_client_errors(client, expression):
    response = client.post("/api/formulas/validate", json={"expression": expression})
    assert response.status_code == 400


def test_copy_builtin_and_constant_only_formula(client):
    builtin = client.get("/api/formulas").json()["data"]["items"][0]
    item = create(
        client,
        builtin["expression"],
        name="我的圆面积",
        parameter_labels=builtin["parameter_labels"],
    )
    assert not item["builtin"]
    assert item["parameter_labels"] == {"r": "半径"}
    constant = create(client, "sqrt(9)")
    assert compute(client, constant, {}).json()["data"]["result"] == "3"
