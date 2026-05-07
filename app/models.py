from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DemoAccountState(Base):
    __tablename__ = 'demo_account_state'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    balance: Mapped[float] = mapped_column(Float, nullable=False)
    equity: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class DemoTradeRecord(Base):
    __tablename__ = 'demo_trades'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    quote_amount: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class DemoPosition(Base):
    __tablename__ = 'demo_positions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False, default='long')
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_entry_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    take_profit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unrealized_pnl_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class BotState(Base):
    __tablename__ = 'bot_state'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trade_mode: Mapped[str] = mapped_column(String(16), nullable=False, default='demo')
    trade_style_mode: Mapped[str] = mapped_column(String(32), nullable=False, default='balanced')
    min_signal_score: Mapped[float] = mapped_column(Float, nullable=False, default=65.0)
    max_open_positions: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    max_quote_per_trade: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    emergency_stop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    live_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_market: Mapped[str] = mapped_column(String(32), nullable=False, default='')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class AiDecision(Base):
    __tablename__ = 'ai_decisions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    indicators_json: Mapped[str] = mapped_column(Text, nullable=False, default='{}')
    executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class NewsSignal(Base):
    __tablename__ = 'news_signals'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False, default='manual')
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sentiment: Mapped[str] = mapped_column(String(16), nullable=False, default='neutral')
    score: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    url: Mapped[str] = mapped_column(String(1024), nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class BotLog(Base):
    __tablename__ = 'bot_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default='info')
    event: Mapped[str] = mapped_column(String(64), nullable=False, default='message')
    message: Mapped[str] = mapped_column(Text, nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False, default='')
    action: Mapped[str] = mapped_column(String(16), nullable=False, default='')
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class MarketRule(Base):
    __tablename__ = 'market_rules'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    base_asset: Mapped[str] = mapped_column(String(16), nullable=False, default='')
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False, default='USDT')
    min_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    min_quote_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    amount_precision: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    price_precision: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    maker_fee_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.002)
    taker_fee_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.002)
    is_trading_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False, default='{}')
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ChartHistoryPoint(Base):
    __tablename__ = 'chart_history'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    balance: Mapped[float] = mapped_column(Float, nullable=False)
    pnl_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    open_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    closed_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class WorkerStrategy(Base):
    __tablename__ = 'worker_strategies'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False, default='1min')
    markets: Mapped[str] = mapped_column(Text, nullable=False, default='BTCUSDT,ETHUSDT')
    last_signal: Mapped[str] = mapped_column(String(32), nullable=False, default='none')
    last_message: Mapped[str] = mapped_column(Text, nullable=False, default='')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class WorkerRunLog(Base):
    __tablename__ = 'worker_run_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='ok')
    message: Mapped[str] = mapped_column(Text, nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class CoinExSettings(Base):
    __tablename__ = 'coinex_settings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    access_id: Mapped[str] = mapped_column(String(256), nullable=False, default='')
    secret_masked: Mapped[str] = mapped_column(String(64), nullable=False, default='')
    base_url: Mapped[str] = mapped_column(String(512), nullable=False, default='https://api.coinex.com/v2')
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default='demo')
    account_type: Mapped[str] = mapped_column(String(32), nullable=False, default='spot')
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class TelegramSettings(Base):
    __tablename__ = 'telegram_settings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    chat_id: Mapped[str] = mapped_column(String(128), nullable=False, default='')
    message_format: Mapped[str] = mapped_column(Text, nullable=False, default='TradeBot: {event}')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class SystemStatus(Base):
    __tablename__ = 'system_status'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    component: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
