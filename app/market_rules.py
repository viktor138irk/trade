import json
import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.coinex import CoinExClient
from app.models import MarketRule


class MarketRuleService:
    def __init__(self, coinex: CoinExClient) -> None:
        self.coinex = coinex

    async def sync(self, db: Session, markets: list[str]) -> dict[str, Any]:
        payload = await self.coinex.get_market_info()
        rows = payload.get('data') or []
        if isinstance(rows, dict):
            rows = [rows]
        wanted = {m.upper() for m in markets}
        synced = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            market = str(row.get('market') or row.get('name') or '').upper()
            if wanted and market not in wanted:
                continue
            if not market:
                continue
            rule = db.query(MarketRule).filter(MarketRule.market == market).first()
            if rule is None:
                rule = MarketRule(market=market)
                db.add(rule)
            rule.base_asset = str(row.get('base_ccy') or row.get('base_currency') or row.get('base') or '').upper()
            rule.quote_asset = str(row.get('quote_ccy') or row.get('quote_currency') or row.get('quote') or 'USDT').upper()
            rule.min_amount = self._float(row.get('min_amount') or row.get('min_base_amount') or row.get('min_asset_amount'), 0.0)
            rule.min_quote_amount = self._float(row.get('min_quote_amount') or row.get('min_amount_value') or row.get('min_value'), 0.0)
            rule.amount_precision = self._int(row.get('amount_precision') or row.get('base_ccy_precision') or row.get('trading_precision'), 8)
            rule.price_precision = self._int(row.get('price_precision') or row.get('quote_ccy_precision'), 8)
            rule.maker_fee_rate = self._float(row.get('maker_fee_rate') or row.get('maker_fee') or row.get('maker'), 0.002)
            rule.taker_fee_rate = self._float(row.get('taker_fee_rate') or row.get('taker_fee') or row.get('taker'), 0.002)
            rule.is_trading_enabled = str(row.get('status') or row.get('state') or 'online').lower() not in {'offline', 'disabled', 'suspend'}
            rule.raw_json = json.dumps(row, ensure_ascii=False)
            rule.synced_at = datetime.now(timezone.utc)
            synced += 1
        db.commit()
        return {'synced': synced, 'markets': list(wanted)}

    def get(self, db: Session, market: str) -> MarketRule | None:
        return db.query(MarketRule).filter(MarketRule.market == market.upper()).first()

    def ensure_amount(self, db: Session, market: str, quote_amount: float, price: float) -> tuple[float, str]:
        rule = self.get(db, market)
        if price <= 0:
            raise ValueError('price must be positive')
        raw_amount = quote_amount / price
        if rule is None:
            return raw_amount, 'Лимиты CoinEx еще не синхронизированы, используется расчет без округления.'
        amount = self.floor_amount(raw_amount, rule.amount_precision)
        min_amount = rule.min_amount or 0.0
        min_quote = rule.min_quote_amount or 0.0
        if min_amount and amount < min_amount:
            raise ValueError(f'amount ниже лимита CoinEx: {amount} < {min_amount}')
        if min_quote and amount * price < min_quote:
            raise ValueError(f'quote amount ниже лимита CoinEx: {amount * price:.8f} < {min_quote}')
        return amount, f'Лимиты CoinEx применены: amount_precision={rule.amount_precision}, min_amount={rule.min_amount}, min_quote={rule.min_quote_amount}, taker_fee={rule.taker_fee_rate}'

    def floor_amount(self, amount: float, precision: int) -> float:
        factor = 10 ** max(0, precision)
        return math.floor(amount * factor) / factor

    def _float(self, value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _int(self, value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
