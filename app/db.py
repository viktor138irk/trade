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
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if 'bot_state' in table_names:
        _add_missing_columns('bot_state', {
            'live_acknowledged': "BOOLEAN NOT NULL DEFAULT FALSE",
            'emergency_stop': "BOOLEAN NOT NULL DEFAULT FALSE",
            'trade_mode': "VARCHAR(16) NOT NULL DEFAULT 'demo'",
            'enabled': "BOOLEAN NOT NULL DEFAULT FALSE",
            'trade_style_mode': "VARCHAR(32) NOT NULL DEFAULT 'balanced'",
            'min_signal_score': "FLOAT NOT NULL DEFAULT 65.0",
            'max_open_positions': "INTEGER NOT NULL DEFAULT 3",
            'max_quote_per_trade': "FLOAT NOT NULL DEFAULT 100.0",
            'last_market': "VARCHAR(32) NOT NULL DEFAULT ''",
        })
    if 'demo_positions' in table_names:
        _add_missing_columns('demo_positions', {
            'side': "VARCHAR(8) NOT NULL DEFAULT 'long'",
            'current_price': "FLOAT NOT NULL DEFAULT 0.0",
            'take_profit': "FLOAT NOT NULL DEFAULT 0.0",
            'stop_loss': "FLOAT NOT NULL DEFAULT 0.0",
            'unrealized_pnl': "FLOAT NOT NULL DEFAULT 0.0",
            'unrealized_pnl_pct': "FLOAT NOT NULL DEFAULT 0.0",
            'opened_at': "TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL",
            'closed_at': "TIMESTAMP WITH TIME ZONE NULL",
        })
    if 'market_rules' in table_names:
        _add_missing_columns('market_rules', {
            'base_asset': "VARCHAR(16) NOT NULL DEFAULT ''",
            'quote_asset': "VARCHAR(16) NOT NULL DEFAULT 'USDT'",
            'min_amount': "FLOAT NOT NULL DEFAULT 0.0",
            'min_quote_amount': "FLOAT NOT NULL DEFAULT 0.0",
            'amount_precision': "INTEGER NOT NULL DEFAULT 8",
            'price_precision': "INTEGER NOT NULL DEFAULT 8",
            'maker_fee_rate': "FLOAT NOT NULL DEFAULT 0.002",
            'taker_fee_rate': "FLOAT NOT NULL DEFAULT 0.002",
            'is_trading_enabled': "BOOLEAN NOT NULL DEFAULT TRUE",
            'raw_json': "TEXT NOT NULL DEFAULT '{}'",
            'synced_at': "TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL",
        })


def _add_missing_columns(table_name: str, columns: dict[str, str]) -> None:
    inspector = inspect(engine)
    existing = {column['name'] for column in inspector.get_columns(table_name)}
    with engine.begin() as conn:
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {name} {ddl}'))
