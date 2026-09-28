"""HTTP boundary: validation, CORS, standardized errors and resource lifecycle."""

import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Path, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StrictStr
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import service
from app.database import connect_database, initialize_database
from app.errors import CalculatorError

load_dotenv()
logger = logging.getLogger(__name__)


class CalculationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expression: StrictStr
    angle_mode: Literal["deg", "rad"] = "deg"


def create_app(database_url: str | None = None) -> FastAPI:
    engine, sessions = connect_database(
        database_url or os.getenv("DATABASE_URL", "sqlite:///./calculator.db")
    )

    @asynccontextmanager
    async def lifespan(application):
        initialize_database(engine)
        yield
        engine.dispose()

    application = FastAPI(
        title="Clarity Calculator API", version="1.0.0", lifespan=lifespan
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            value.strip()
            for value in os.getenv(
                "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if value.strip()
        ],
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

    def get_session():
        with sessions() as session:
            try:
                yield session
            except Exception:
                session.rollback()
                raise

    @application.exception_handler(CalculatorError)
    async def calculation_error(request, exc):
        return JSONResponse(
            status_code=exc.status,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    **(
                        {"position": exc.position, "end_position": exc.end_position}
                        if exc.position is not None
                        else {}
                    ),
                },
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {"code": "INVALID_REQUEST", "message": "请求格式或参数无效。"},
            },
        )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        logger.error("Database operation failed: %s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "数据库暂不可用，请稍后重试。",
                },
            },
        )

    @application.get("/api/health")
    def health(session: Annotated[Session, Depends(get_session)]):
        session.execute(text("SELECT 1"))
        return {"success": True, "data": {"status": "ok", "database": "connected"}}

    @application.post("/api/calculate", status_code=201)
    def calculate(
        body: CalculationRequest, session: Annotated[Session, Depends(get_session)]
    ):
        return {
            "success": True,
            "data": service.calculate_and_save(
                session, body.expression, body.angle_mode
            ),
        }

    @application.get("/api/history")
    def history(
        session: Annotated[Session, Depends(get_session)],
        q: str = Query("", max_length=500),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ):
        return {
            "success": True,
            "data": service.list_history(session, q.strip(), page, page_size),
        }

    @application.delete("/api/history/{record_id}")
    def delete(
        session: Annotated[Session, Depends(get_session)], record_id: int = Path(ge=1)
    ):
        return {"success": True, "data": service.delete_history(session, record_id)}

    return application


app = create_app()
