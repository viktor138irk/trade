import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.ai_bot import AiTradingBot, decision_to_dict
from app.demo_account import DemoAccountService
from app.legacy_bot import LegacyBotService
from app.market_rules import MarketRuleService
from app.models import BotLog


class SignalMonitor:
    def __init__(self, ai_bot: AiTradingBot, demo_service: DemoAccountService, legacy_bot: LegacyBotService, market_rules: MarketRuleService) -> None:
        self.ai_bot = ai_bot
        self.demo_service = demo_service
        self.legacy_bot = legacy_bot
        self.market_rules = market_rules
        self.running = False
        self.last_status = 'Остановлен'
        self.last_market = ''
        self.last_action = ''
        self.last_score = 0.0
        self.last_error = ''
        self.last_run_at: datetime | None = None
        self.rules_synced = False

    def status(self) -> dict[str, Any]:
        return {
            'running': self.running,
            'status': self.last_status,
            'last_market': self.last_market,
            'last_action': self.last_action,
            'last_score': self.last_score,
            'last_error': self.last_error,
            'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None,
            'rules_synced': self.rules_synced,
            'markets_count': len(self.ai_bot.markets),
        }

    async def loop(self, session_factory, interval_seconds: int = 10) -> None:
        self.running = True
        self.last_status = 'Запущен'
        with session_factory() as db:
            self.write_log(db, 'info', 'monitor_started', 'Мониторинг автоторговли запущен. Бот без остановки ищет выгодные сделки.')
        while self.running:
            try:
                with session_factory() as db:
                    await self.tick(db)
            except Exception as exc:  # noqa: BLE001 - monitor must not kill the app
                self.last_error = str(exc)
                self.last_status = 'Ошибка мониторинга'
                with session_factory() as db:
                    self.write_log(db, 'error', 'monitor_error', f'Ошибка мониторинга: {exc}')
            await asyncio.sleep(interval_seconds)

    def stop(self) -> None:
        self.running = False
        self.last_status = 'Остановлен'

    async def tick(self, db: Session) -> dict[str, Any]:
        state = self.ai_bot.get_or_create_state(db)
        self.last_run_at = datetime.now(timezone.utc)
        if not self.rules_synced:
            try:
                result = await self.market_rules.sync(db, None)
                active_markets = self.market_rules.active_markets(db, fallback=self.ai_bot.markets)
                if active_markets:
                    self.ai_bot.markets = active_markets
                self.rules_synced = True
                self.write_log(db, 'success', 'coinex_rules_synced', f'Синхронизированы лимиты и комиссии CoinEx: {result["synced"]} рынков. Активных рынков в работе: {len(self.ai_bot.markets)}.')
            except Exception as exc:  # noqa: BLE001
                self.write_log(db, 'warning', 'coinex_rules_sync_failed', f'Не удалось синхронизировать лимиты CoinEx: {exc}')

        if not state.enabled:
            self.last_status = 'Бот выключен'
            self.write_log(db, 'warning', 'bot_disabled', 'Мониторинг проверил состояние: бот выключен, сделка не открывается.')
            return self.status()
        if state.emergency_stop:
            self.last_status = 'Emergency stop'
            self.write_log(db, 'warning', 'emergency_stop', 'Аварийная остановка активна. Новые сделки не открываются.')
            return self.status()

        self.write_log(db, 'info', 'scan_started', f'Сканирую рынки по ротации: {len(self.ai_bot.markets)} активных CoinEx-маркетов, пары с открытой сделкой пропускаю.')
        decision = await self.ai_bot.make_decision(db, None, skip_open_positions=True)
        data = decision_to_dict(decision)
        self.last_market = decision.market
        self.last_action = decision.action
        self.last_score = decision.score
        action_ru = {'buy': 'покупка', 'sell': 'продажа', 'hold': 'ожидание'}.get(decision.action, decision.action)
        self.write_log(db, 'info', 'signal_found', f'Найден сигнал: {decision.market}, действие: {action_ru}, оценка AI: {decision.score:.1f}/100.', market=decision.market, action=decision.action, score=decision.score)

        if state.trade_mode == 'demo' and decision.action == 'buy' and decision.score >= state.min_signal_score:
            price = float(data['indicators']['last_price'])
            amount, rule_message = self.market_rules.ensure_amount(db, decision.market, max(1.0, state.max_quote_per_trade), price)
            trade = self.demo_service.add_demo_trade(db, decision.market, 'buy', price, amount, f'{decision.reason}; {rule_message}')
            decision.executed = True
            db.add(decision)
            db.commit()
            self.legacy_bot.snapshot_history(db)
            self.last_status = f'Открыта демо-сделка BUY {trade.market}'
            self.write_log(db, 'success', 'demo_order_opened', f'Открыта демо-сделка: BUY {trade.market}, сумма {trade.quote_amount:.2f} USDT, цена {trade.price:.8f}. {rule_message}', market=trade.market, action=trade.side, score=decision.score)
        elif state.trade_mode == 'demo' and decision.action == 'sell' and decision.score >= state.min_signal_score:
            price = float(data['indicators']['last_price'])
            if self.demo_service.has_open_position(db, decision.market):
                trade = self.demo_service.close_full_market(db, decision.market, price, decision.reason)
                self.legacy_bot.snapshot_history(db)
                self.last_status = f'Закрыта вся позиция SELL {trade.market}'
                self.write_log(db, 'success', 'demo_order_closed', f'Закрыта вся доступная позиция: SELL {trade.market}, объем {trade.amount:g}, цена {trade.price:.8f}.', market=trade.market, action='sell', score=decision.score)
            else:
                self.last_status = 'SELL сигнал без открытой позиции'
                self.write_log(db, 'info', 'sell_without_position', f'SELL сигнал по {decision.market}, но открытой позиции нет — пропускаю.', market=decision.market, action='sell', score=decision.score)
        elif state.trade_mode == 'live' and decision.action in {'buy', 'sell'} and decision.score >= state.min_signal_score:
            self.last_status = 'Live-сигнал готов к исполнению'
            self.write_log(db, 'warning', 'live_signal_ready', f'Live-сигнал найден: {decision.market}, {action_ru}, оценка {decision.score:.1f}. Требуется live-order adapter CoinEx: сверить баланс и отправить ордер.', market=decision.market, action=decision.action, score=decision.score)
        else:
            self.last_status = 'Сигнал слабый, сделка не открыта'
            self.write_log(db, 'info', 'signal_skipped', f'Сделка пропущена: {decision.market}, оценка {decision.score:.1f}, минимум {state.min_signal_score:.1f}.', market=decision.market, action=decision.action, score=decision.score)
        return self.status()

    def write_log(self, db: Session, level: str, event: str, message: str, market: str = '', action: str = '', score: float = 0.0) -> None:
        db.add(BotLog(level=level, event=event, message=message, market=market, action=action, score=score))
        db.commit()

    def recent_logs(self, db: Session, limit: int = 100) -> list[dict[str, Any]]:
        rows = db.query(BotLog).order_by(BotLog.id.desc()).limit(limit).all()
        return [{'id': row.id, 'level': row.level, 'event': row.event, 'message': row.message, 'market': row.market, 'action': row.action, 'score': row.score, 'created_at': row.created_at.isoformat()} for row in rows]
