"""ASGI API for Workers, using D1 bindings and the existing calculation engine."""

import json
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StrictStr

from app.errors import CalculatorError
from app.formula_rules import (
    FormulaCalculation,
    FormulaRequest,
    SyntaxRequest,
    builtin_items,
    check_revision,
    inspect_formula,
    values_for,
)
from app.parser import MAX_LENGTH, Parser, calculate

app = FastAPI(title="Calculator Cloudflare API", version="1.0.0")


class CalculationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expression: StrictStr
    angle_mode: Literal["deg", "rad"] = "deg"


@app.exception_handler(CalculatorError)
async def calculator_error(request, exc):
    error = {"code": exc.code, "message": exc.message}
    if exc.parameter:
        error["parameter"] = exc.parameter
    if exc.position is not None:
        error.update(position=exc.position, end_position=exc.end_position)
    return JSONResponse(
        status_code=exc.status, content={"success": False, "error": error}
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error": {
                "code": "INVALID_REQUEST",
                "message": "请求格式或参数无效。",
            },
        },
    )


@app.middleware("http")
async def no_cache(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


async def rows(request, sql, *parameters):
    """Only bind values; never interpolate user input into SQL."""
    try:
        db = request.scope["env"].DB
        statement = db.prepare(sql)
        if parameters:
            statement = statement.bind(*parameters)
        response = await statement.run()
        result = response.to_py() if hasattr(response, "to_py") else response
        if not result["success"]:
            raise RuntimeError("D1 query failed")
        return result["results"]
    except Exception as exc:
        raise CalculatorError(
            "DATABASE_UNAVAILABLE", "数据库暂不可用，请稍后重试。", 503
        ) from exc


async def calculate_and_save(request, expression, angle_mode):
    normalized, result, steps = calculate(expression, angle_mode)
    records = await rows(
        request,
        "INSERT INTO calculation_history (expression,result,angle_mode,created_at) "
        "VALUES (?,?,?,?) RETURNING *",
        normalized,
        result,
        angle_mode,
        datetime.now(UTC).isoformat(),
    )
    return {**records[0], "steps": steps}


@app.get("/api/health")
async def health(request: Request):
    await rows(request, "SELECT 1")
    return {"success": True, "data": {"status": "ok", "database": "connected"}}


@app.post("/api/calculate", status_code=201)
async def compute(request: Request, body: CalculationRequest):
    return {
        "success": True,
        "data": await calculate_and_save(request, body.expression, body.angle_mode),
    }


@app.get("/api/history")
async def history(
    request: Request,
    q: str = Query("", max_length=500),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = q.strip()
    where = " WHERE instr(expression, ?) > 0 OR instr(result, ?) > 0" if query else ""
    parameters = (query, query) if query else ()
    total = await rows(
        request,
        "SELECT count(*) AS total FROM calculation_history" + where,
        *parameters,
    )
    items = await rows(
        request,
        "SELECT * FROM calculation_history"
        + where
        + " ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
        *parameters,
        page_size,
        (page - 1) * page_size,
    )
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total[0]["total"],
            "page": page,
            "page_size": page_size,
        },
    }


@app.delete("/api/history/{record_id}")
async def delete_history(request: Request, record_id: int = Path(ge=1)):
    deleted = await rows(
        request, "DELETE FROM calculation_history WHERE id=? RETURNING id", record_id
    )
    if not deleted:
        raise CalculatorError("NOT_FOUND", "这条记录不存在或已被删除。", 404)
    return {"success": True, "data": {"deleted_id": record_id}}


def formula_item(record):
    return {
        **record,
        "id": str(record["id"]),
        "builtin": False,
        "parameter_labels": json.loads(record["parameter_labels"]),
        "parameters": inspect_formula(record["expression"]),
    }


async def get_formula(request, formula_id):
    for item in builtin_items():
        if item["id"] == formula_id:
            return item
    records = []
    if formula_id.isascii() and formula_id.isdigit() and len(formula_id) < 10:
        records = await rows(
            request, "SELECT * FROM formulas WHERE id=?", int(formula_id)
        )
    if not records:
        raise CalculatorError("NOT_FOUND", "公式已被删除，请刷新列表。", 404)
    return formula_item(records[0])


@app.get("/api/formulas")
async def formulas(request: Request, q: str = Query("", max_length=40)):
    records = await rows(
        request, "SELECT * FROM formulas ORDER BY updated_at DESC,id DESC"
    )
    items = builtin_items() + [formula_item(record) for record in records]
    return {
        "success": True,
        "data": {
            "items": [
                item
                for item in items
                if q.strip().casefold() in item["name"].casefold()
            ]
        },
    }


@app.post("/api/formulas/validate")
async def validate(body: SyntaxRequest):
    return {"success": True, "data": {"parameters": inspect_formula(body.expression)}}


@app.post("/api/formulas", status_code=201)
async def create_formula(request: Request, body: FormulaRequest):
    values = values_for(body)
    now = datetime.now(UTC).isoformat()
    records = await rows(
        request,
        "INSERT INTO formulas "
        "(name,expression,parameter_labels,angle_mode,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?) RETURNING *",
        values["name"],
        values["expression"],
        json.dumps(values["parameter_labels"], ensure_ascii=False),
        values["angle_mode"],
        now,
        now,
    )
    return {"success": True, "data": formula_item(records[0])}


@app.put("/api/formulas/{formula_id}")
async def edit_formula(request: Request, formula_id: str, body: FormulaRequest):
    item = await get_formula(request, formula_id)
    if item["builtin"]:
        raise CalculatorError("READ_ONLY", "内置公式请另存为自定义公式。", 403)
    check_revision(item, body.updated_at)
    values = values_for(body)
    now = max(
        datetime.now(UTC),
        datetime.fromisoformat(item["updated_at"]) + timedelta(microseconds=1),
    ).isoformat()
    records = await rows(
        request,
        "UPDATE formulas SET name=?,expression=?,parameter_labels=?,"
        "angle_mode=?,updated_at=? "
        "WHERE id=? AND updated_at=? RETURNING *",
        values["name"],
        values["expression"],
        json.dumps(values["parameter_labels"], ensure_ascii=False),
        values["angle_mode"],
        now,
        int(formula_id),
        body.updated_at,
    )
    if not records:
        raise CalculatorError("FORMULA_CONFLICT", "公式已被修改，请重新打开。", 409)
    return {"success": True, "data": formula_item(records[0])}


@app.delete("/api/formulas/{formula_id}")
async def delete_formula(
    request: Request, formula_id: str, updated_at: str = Query(..., max_length=50)
):
    item = await get_formula(request, formula_id)
    if item["builtin"]:
        raise CalculatorError("READ_ONLY", "内置公式不能删除。", 403)
    check_revision(item, updated_at)
    records = await rows(
        request,
        "DELETE FROM formulas WHERE id=? AND updated_at=? RETURNING id",
        int(formula_id),
        updated_at,
    )
    if not records:
        raise CalculatorError("FORMULA_CONFLICT", "公式已被修改，请刷新列表。", 409)
    return {"success": True, "data": {"deleted_id": formula_id}}


@app.post("/api/formulas/{formula_id}/calculate", status_code=201)
async def compute_formula(request: Request, formula_id: str, body: FormulaCalculation):
    item = await get_formula(request, formula_id)
    check_revision(item, body.updated_at)
    if set(body.parameters) != set(item["parameters"]):
        raise CalculatorError(
            "INVALID_PARAMETERS", "请填写全部参数，不要添加额外参数。"
        )
    for name, expression in body.parameters.items():
        try:
            calculate(expression, body.angle_mode)
        except CalculatorError as error:
            error.parameter = name
            raise
    expanded = "".join(
        "(" + body.parameters[token] + ")" if token in body.parameters else token
        for token in Parser(item["expression"]).tokens
    )
    if len(expanded) > MAX_LENGTH:
        raise CalculatorError(
            "EXPRESSION_TOO_LONG", "代入后的表达式不能超过 500 个字符。"
        )
    return {
        "success": True,
        "data": await calculate_and_save(request, expanded, body.angle_mode),
    }
