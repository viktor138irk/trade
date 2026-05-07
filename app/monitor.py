import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.ai_bot import AiTradingBot, decision_to_dict
from app.demo_account import DemoAccountService
from app.legacy_bot import LegacyBotService


class SignalMonitor:
    def __init__(self, ai_bot: AiTradingBot, demo_service: DemoAccountService, legacy_bot: LegacyBotService) -> None:
        self.ai_bot = ai_bot
        self.demo_service = demo_service
        self.legacy_bot = legacy_bot
        self.running = False
        self.last_status = 'Остановлен'
        self.last_market = ''
        self.last_action = ''
        self.last_score = 0.0
        self.last_error = ''
        self.last_run_at: datetime | None = None

    def status(self) -> dict[str, Any]:
        return {
            'running': self.running,
            'status': self.last_status,
            'last_market': self.last_market,
            'last_action': self.last_action,
            'last_score': self.last_score,
            'last_error': self.last_error,
            'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None,
        }

    async def loop(self, session_factory, interval_seconds: int = 20) -> None:
        self.running = True
        self.last_status = 'Запущен'
        while self.running:
            try:
                with session_factory() as db:
                    await self.tick(db)
            except Exception as exc:  # noqa: BLE001 - monitor must not kill the app
                self.last_error = str(exc)
                self.last_status = 'Ошибка мониторинга'
            await asyncio.sleep(interval_seconds)

    def stop(self) -> None:
        self.running = False
        self.last_status = 'Остановлен'

    async def tick(self, db: Session) -> dict[str, Any]:
        state = self.ai_bot.get_or_create_state(db)
        self.last_run_at = datetime.now(timezone.utc)
        if not state.enabled:
            self.last_status = 'Бот выключен'
            return self.status()
        if state.emergency_stop:
            self.last_status = 'Emergency stop'
            return self.status()

        decision = await self.ai_bot.make_decision(db, None)
        data = decision_to_dict(decision)
        self.last_market = decision.market
        self.last_action = decision.action
        self.last_score = decision.score

        if state.trade_mode == 'demo' and decision.action in {'buy', 'sell'} and decision.score >= state.min_signal_score:
            price = float(data['indicators']['last_price'])
            amount = max(1.0, state.max_quote_per_trade) / price
            trade = self.demo_service.add_demo_trade(db, decision.market, decision.action, price, amount, decision.reason)
            decision.executed = True
            db.add(decision)
            db.commit()
            self.legacy_bot.snapshot_history(db)
            self.last_status = f'Открыта демо-сделка {trade.side.upper()} {trade.market}'
        elif state.trade_mode == 'live':
            self.last_status = 'Найден live-сигнал, ожидает live adapter'
        else:
            self.last_status = 'Сигнал слабый, сделка не открыта'
        return self.status()
