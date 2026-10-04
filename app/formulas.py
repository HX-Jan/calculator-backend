"""Shared formula storage with syntax-only validation and safe evaluation."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.database import Formula
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
from app.service import calculate_and_save


def get_formula(session, formula_id):
    for item in builtin_items():
        if item["id"] == formula_id:
            return item
    record = (
        session.get(Formula, int(formula_id))
        if formula_id.isascii() and formula_id.isdigit() and len(formula_id) < 10
        else None
    )
    if record is None:
        raise CalculatorError("NOT_FOUND", "公式已被删除，请刷新列表。", 404)
    return {**record.as_dict(), "parameters": inspect_formula(record.expression)}


def install_formula_routes(app, get_session):
    @app.get("/api/formulas")
    def listing(
        session: Annotated[Session, Depends(get_session)],
        q: str = Query("", max_length=40),
    ):
        records = session.scalars(
            select(Formula).order_by(Formula.updated_at.desc(), Formula.id.desc())
        )
        items = builtin_items() + [
            {**record.as_dict(), "parameters": inspect_formula(record.expression)}
            for record in records
        ]
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
    def validate(body: SyntaxRequest):
        return {
            "success": True,
            "data": {"parameters": inspect_formula(body.expression)},
        }

    @app.post("/api/formulas", status_code=201)
    def create(body: FormulaRequest, session: Annotated[Session, Depends(get_session)]):
        record = Formula(**values_for(body))
        session.add(record)
        session.commit()
        return {"success": True, "data": get_formula(session, str(record.id))}

    @app.put("/api/formulas/{formula_id}")
    def edit(
        formula_id: str,
        body: FormulaRequest,
        session: Annotated[Session, Depends(get_session)],
    ):
        item = get_formula(session, formula_id)
        if item["builtin"]:
            raise CalculatorError("READ_ONLY", "内置公式请另存为自定义公式。", 403)
        check_revision(item, body.updated_at)
        old = datetime.fromisoformat(item["updated_at"])
        now = max(datetime.now(UTC), old + timedelta(microseconds=1))
        changed = session.execute(
            update(Formula)
            .where(Formula.id == int(formula_id), Formula.updated_at == old)
            .values(**values_for(body), updated_at=now)
        )
        if changed.rowcount != 1:
            raise CalculatorError("FORMULA_CONFLICT", "公式已被修改，请重新打开。", 409)
        session.commit()
        return {"success": True, "data": get_formula(session, formula_id)}

    @app.delete("/api/formulas/{formula_id}")
    def remove(
        formula_id: str,
        session: Annotated[Session, Depends(get_session)],
        updated_at: str = Query(..., max_length=50),
    ):
        item = get_formula(session, formula_id)
        if item["builtin"]:
            raise CalculatorError("READ_ONLY", "内置公式不能删除。", 403)
        check_revision(item, updated_at)
        changed = session.execute(
            delete(Formula).where(
                Formula.id == int(formula_id),
                Formula.updated_at == datetime.fromisoformat(item["updated_at"]),
            )
        )
        if changed.rowcount != 1:
            raise CalculatorError("FORMULA_CONFLICT", "公式已被修改，请刷新列表。", 409)
        session.commit()
        return {"success": True, "data": {"deleted_id": formula_id}}

    @app.post("/api/formulas/{formula_id}/calculate", status_code=201)
    def compute(
        formula_id: str,
        body: FormulaCalculation,
        session: Annotated[Session, Depends(get_session)],
    ):
        item = get_formula(session, formula_id)
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
        # Replace whole tokens; preserve constants, exponents and function names.
        parser = Parser(item["expression"])
        expanded = "".join(
            "(" + body.parameters[token] + ")" if token in body.parameters else token
            for token in parser.tokens
        )
        if len(expanded) > MAX_LENGTH:
            raise CalculatorError(
                "EXPRESSION_TOO_LONG", "代入后的表达式不能超过 500 个字符。"
            )
        return {
            "success": True,
            "data": calculate_and_save(session, expanded, body.angle_mode),
        }
