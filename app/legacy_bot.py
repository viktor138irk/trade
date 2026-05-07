from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    AiDecision,
    ChartHistoryPoint,
    CoinExSettings,
    DemoAccountState,
    DemoPosition,
    DemoTradeRecord,
    SystemStatus,
    TelegramSettings,
    WorkerRunLog,
    WorkerStrategy,
)


DEFAULT_STRATEGIES = [
    ('AI News Scalper', '1min', 'ALL_USDT'),
    ('Trend Follow', '5min', 'ALL_USDT'),
    ('Volatility Catcher', '1min', 'ALL_USDT'),
]


class LegacyBotService:
    def ensure_defaults(self, db: Session) -> None:
        if db.get(CoinExSettings, 1) is None:
            db.add(CoinExSettings(id=1))
        if db.get(TelegramSettings, 1) is None:
            db.add(TelegramSettings(id=1))
        for name, timeframe, markets in DEFAULT_STRATEGIES:
            exists = db.query(WorkerStrategy).filter(WorkerStrategy.name == name).first()
            if exists is None:
                db.add(WorkerStrategy(name=name, timeframe=timeframe, markets=markets, enabled=False, dry_run=True))
        db.commit()

    def dashboard(self, db: Session) -> dict[str, Any]:
        self.ensure_defaults(db)
        account = db.get(DemoAccountState, 1)
        balance = account.balance if account else 0.0
        realized = account.realized_pnl if account else 0.0
        unrealized = sum(item.unrealized_pnl for item in db.query(DemoPosition).filter(DemoPosition.is_open.is_(True)).all())
        open_value = sum(item.current_price * item.amount for item in db.query(DemoPosition).filter(DemoPosition.is_open.is_(True)).all())
        equity = balance + open_value
        trades_total = db.query(DemoTradeRecord).count()
        open_positions = db.query(DemoPosition).filter(DemoPosition.is_open.is_(True)).count()
        closed_positions = db.query(DemoPosition).filter(DemoPosition.is_open.is_(False)).count()
        latest_decision = db.query(AiDecision).order_by(AiDecision.id.desc()).first()
        strategies = db.query(WorkerStrategy).order_by(WorkerStrategy.id.asc()).all()
        coinex = db.get(CoinExSettings, 1)
        telegram = db.get(TelegramSettings, 1)
        return {
            'kpi': {
                'balance': balance,
                'equity': equity,
                'realized_pnl': realized,
                'unrealized_pnl': unrealized,
                'total_pnl': realized + unrealized,
                'open_positions_value': open_value,
                'trades_total': trades_total,
                'open_positions': open_positions,
                'closed_positions': closed_positions,
                'active_strategies': sum(1 for s in strategies if s.enabled),
            },
            'latest_decision': self._decision(latest_decision),
            'strategies': [self._strategy(s) for s in strategies],
            'coinex': self._coinex(coinex),
            'telegram': self._telegram(telegram),
        }

    def open_positions(self, db: Session) -> list[dict[str, Any]]:
        positions = db.query(DemoPosition).filter(DemoPosition.is_open.is_(True)).order_by(DemoPosition.id.desc()).all()
        return [self._position(item) for item in positions]

    def closed_positions(self, db: Session, limit: int = 50) -> list[dict[str, Any]]:
        positions = db.query(DemoPosition).filter(DemoPosition.is_open.is_(False)).order_by(DemoPosition.id.desc()).limit(limit).all()
        return [self._position(item) for item in positions]

    def chart_history(self, db: Session, limit: int = 100) -> list[dict[str, Any]]:
        rows = db.query(ChartHistoryPoint).order_by(ChartHistoryPoint.id.desc()).limit(limit).all()
        return [
            {
                'time': int(row.created_at.timestamp()),
                'balance': row.balance,
                'pnl_total': row.pnl_total,
                'open_trades': row.open_trades,
                'closed_trades': row.closed_trades,
            }
            for row in reversed(rows)
        ]

    def snapshot_history(self, db: Session) -> dict[str, Any]:
        dash = self.dashboard(db)
        point = ChartHistoryPoint(
            balance=dash['kpi']['equity'],
            pnl_total=dash['kpi']['total_pnl'],
            open_trades=dash['kpi']['open_positions'],
            closed_trades=dash['kpi']['closed_positions'],
        )
        db.add(point)
        db.commit()
        db.refresh(point)
        return {'id': point.id, 'balance': point.balance, 'pnl_total': point.pnl_total}

    def update_strategy(self, db: Session, strategy_id: int, enabled: bool | None = None, dry_run: bool | None = None) -> dict[str, Any]:
        self.ensure_defaults(db)
        strategy = db.get(WorkerStrategy, strategy_id)
        if strategy is None:
            raise ValueError('strategy not found')
        if enabled is not None:
            strategy.enabled = enabled
        if dry_run is not None:
            strategy.dry_run = dry_run
        strategy.last_signal = 'waiting' if strategy.enabled else 'stopped'
        strategy.last_message = 'Strategy settings updated from dashboard'
        db.add(strategy)
        db.add(WorkerRunLog(strategy_name=strategy.name, status='ok', message=strategy.last_message))
        db.commit()
        db.refresh(strategy)
        return self._strategy(strategy)

    def update_coinex(self, db: Session, enabled: bool | None = None, access_id: str | None = None, secret_key: str | None = None, mode: str | None = None) -> dict[str, Any]:
        self.ensure_defaults(db)
        settings = db.get(CoinExSettings, 1)
        if enabled is not None:
            settings.enabled = enabled
        if access_id is not None:
            settings.access_id = access_id
        if secret_key is not None and secret_key:
            settings.secret_masked = self._mask(secret_key)
        if mode is not None:
            settings.mode = mode
        db.add(settings)
        db.commit()
        db.refresh(settings)
        return self._coinex(settings)

    def update_telegram(self, db: Session, enabled: bool | None = None, chat_id: str | None = None, message_format: str | None = None) -> dict[str, Any]:
        self.ensure_defaults(db)
        settings = db.get(TelegramSettings, 1)
        if enabled is not None:
            settings.enabled = enabled
        if chat_id is not None:
            settings.chat_id = chat_id
        if message_format is not None:
            settings.message_format = message_format
        db.add(settings)
        db.commit()
        db.refresh(settings)
        return self._telegram(settings)

    def updater_status(self, db: Session) -> dict[str, Any]:
        db.add(SystemStatus(component='updater', status='ok', message='Updater ready. Manual git pull is available on server.'))
        db.commit()
        return {'status': 'ready', 'message': 'Обновление готово: git pull + docker compose up -d --build'}

    def terminal_command(self, command: str) -> dict[str, Any]:
        allowed = {'status', 'health', 'version'}
        if command not in allowed:
            return {'status': 'blocked', 'output': 'Разрешены команды: status, health, version'}
        return {'status': 'ok', 'output': f'Команда {command} выполнена в безопасном режиме панели'}

    def android_status(self, db: Session) -> dict[str, Any]:
        dash = self.dashboard(db)
        return {
            'ok': True,
            'mode': dash['coinex']['mode'],
            'balance': dash['kpi']['balance'],
            'equity': dash['kpi']['equity'],
            'pnl': dash['kpi']['total_pnl'],
            'open_positions': dash['kpi']['open_positions'],
            'active_strategies': dash['kpi']['active_strategies'],
        }

    def _position(self, position: DemoPosition) -> dict[str, Any]:
        return {
            'id': position.id,
            'market': position.market,
            'side': position.side,
            'amount': position.amount,
            'avg_entry_price': position.avg_entry_price,
            'current_price': position.current_price,
            'take_profit': position.take_profit,
            'stop_loss': position.stop_loss,
            'unrealized_pnl': position.unrealized_pnl,
            'unrealized_pnl_pct': position.unrealized_pnl_pct,
            'realized_pnl': position.realized_pnl,
            'is_open': position.is_open,
        }

    def _strategy(self, strategy: WorkerStrategy) -> dict[str, Any]:
        return {
            'id': strategy.id,
            'name': strategy.name,
            'enabled': strategy.enabled,
            'dry_run': strategy.dry_run,
            'timeframe': strategy.timeframe,
            'markets': strategy.markets,
            'last_signal': strategy.last_signal,
            'last_message': strategy.last_message,
        }

    def _decision(self, decision: AiDecision | None) -> dict[str, Any] | None:
        if decision is None:
            return None
        return {
            'market': decision.market,
            'action': decision.action,
            'score': decision.score,
            'confidence': decision.confidence,
            'reason': decision.reason,
        }

    def _coinex(self, settings: CoinExSettings | None) -> dict[str, Any]:
        if settings is None:
            return {'enabled': False, 'mode': 'demo', 'access_id': '', 'secret_masked': ''}
        return {
            'enabled': settings.enabled,
            'mode': settings.mode,
            'access_id': settings.access_id,
            'secret_masked': settings.secret_masked,
            'base_url': settings.base_url,
            'account_type': settings.account_type,
        }

    def _telegram(self, settings: TelegramSettings | None) -> dict[str, Any]:
        if settings is None:
            return {'enabled': False, 'chat_id': ''}
        return {'enabled': settings.enabled, 'chat_id': settings.chat_id, 'message_format': settings.message_format}

    def _mask(self, value: str) -> str:
        if len(value) <= 8:
            return '***'
        return f'{value[:4]}***{value[-4:]}'
