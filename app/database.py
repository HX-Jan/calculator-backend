"""Persistent storage, shared by SQLite development and PostgreSQL deployment."""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class History(Base):
    __tablename__ = "calculation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expression: Mapped[str] = mapped_column(String(500))
    angle_mode: Mapped[str] = mapped_column(
        String(3), default="deg", server_default="deg"
    )
    result: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )

    def as_dict(self) -> dict:
        timestamp = self.created_at
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return {
            "id": self.id,
            "expression": self.expression,
            "result": self.result,
            "angle_mode": self.angle_mode,
            "created_at": timestamp.isoformat(),
        }


class Formula(Base):
    __tablename__ = "formulas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    expression: Mapped[str] = mapped_column(String(500))
    parameter_labels: Mapped[dict] = mapped_column(JSON)
    angle_mode: Mapped[str] = mapped_column(String(3), default="deg")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    def as_dict(self):
        def stamp(value):
            return (
                value.replace(tzinfo=UTC) if value.tzinfo is None else value
            ).isoformat()

        return {
            "id": str(self.id),
            "name": self.name,
            "expression": self.expression,
            "parameter_labels": self.parameter_labels,
            "angle_mode": self.angle_mode,
            "created_at": stamp(self.created_at),
            "updated_at": stamp(self.updated_at),
            "builtin": False,
        }


def connect_database(url: str):
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    options = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=options, pool_pre_ping=True)
    return engine, sessionmaker(engine, expire_on_commit=False)


def initialize_database(engine):
    """Additive, repeatable upgrade for databases created before scientific mode."""
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(620530837)"))
        history_columns = inspect(connection).get_columns("calculation_history")
        columns = {column["name"] for column in history_columns}
        if engine.dialect.name == "postgresql":
            result_type = next(
                column["type"]
                for column in history_columns
                if column["name"] == "result"
            )
            if isinstance(result_type, String) and result_type.length is not None:
                connection.execute(
                    text(
                        "ALTER TABLE calculation_history ALTER COLUMN result TYPE TEXT"
                    )
                )
        if "angle_mode" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE calculation_history ADD COLUMN "
                    "angle_mode VARCHAR(3) NOT NULL DEFAULT 'deg'"
                )
            )
