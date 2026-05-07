from collections.abc import Generator
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    apply_safe_schema_patches()


def apply_safe_schema_patches() -> None:
    """Tiny compatibility layer for the early MVP.

    SQLAlchemy create_all creates missing tables but does not alter existing ones.
    During rapid MVP iterations this keeps old server databases from breaking
    when a new column is added.
    """
    inspector = inspect(engine)
    if 'bot_state' in inspector.get_table_names():
        existing = {column['name'] for column in inspector.get_columns('bot_state')}
        patches = []
        if 'live_acknowledged' not in existing:
            patches.append("ALTER TABLE bot_state ADD COLUMN live_acknowledged BOOLEAN NOT NULL DEFAULT FALSE")
        if 'emergency_stop' not in existing:
            patches.append("ALTER TABLE bot_state ADD COLUMN emergency_stop BOOLEAN NOT NULL DEFAULT FALSE")
        if 'trade_mode' not in existing:
            patches.append("ALTER TABLE bot_state ADD COLUMN trade_mode VARCHAR(16) NOT NULL DEFAULT 'demo'")
        if 'enabled' not in existing:
            patches.append("ALTER TABLE bot_state ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT FALSE")
        if 'trade_style_mode' not in existing:
            patches.append("ALTER TABLE bot_state ADD COLUMN trade_style_mode VARCHAR(32) NOT NULL DEFAULT 'balanced'")
        if 'min_signal_score' not in existing:
            patches.append("ALTER TABLE bot_state ADD COLUMN min_signal_score FLOAT NOT NULL DEFAULT 65.0")
        if 'max_open_positions' not in existing:
            patches.append("ALTER TABLE bot_state ADD COLUMN max_open_positions INTEGER NOT NULL DEFAULT 3")
        if 'max_quote_per_trade' not in existing:
            patches.append("ALTER TABLE bot_state ADD COLUMN max_quote_per_trade FLOAT NOT NULL DEFAULT 100.0")
        with engine.begin() as conn:
            for patch in patches:
                conn.execute(text(patch))
