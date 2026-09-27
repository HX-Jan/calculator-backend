"""Calculation and history use cases; database commit precedes API success."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import History
from app.errors import CalculatorError
from app.parser import calculate


def calculate_and_save(session: Session, expression: str) -> dict:
    normalized, result, steps = calculate(expression)
    record = History(expression=normalized, result=result)
    session.add(record)
    session.commit()
    return {**record.as_dict(), "steps": steps}


def list_history(session: Session, query: str, page: int, page_size: int) -> dict:
    conditions = []
    if query:
        conditions.append(
            or_(
                History.expression.contains(query, autoescape=True),
                History.result.contains(query, autoescape=True),
            )
        )
    total = session.scalar(select(func.count()).select_from(History).where(*conditions))
    records = session.scalars(
        select(History)
        .where(*conditions)
        .order_by(History.created_at.desc(), History.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "items": [record.as_dict() for record in records],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def delete_history(session: Session, record_id: int) -> dict:
    record = session.get(History, record_id)
    if record is None:
        raise CalculatorError("NOT_FOUND", "这条记录不存在或已被删除。", 404)
    session.delete(record)
    session.commit()
    return {"deleted_id": record_id}
