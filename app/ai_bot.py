import json
import statistics
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.coinex import CoinExClient
from app.models import AiDecision, BotState, DemoPosition, DemoTradeRecord, NewsSignal


@dataclass
class IndicatorPack:
    market: str
    last_price: float
    sma_fast: float
    sma_slow: float
    momentum_pct: float
    volatility_pct: float
    news_score: float
    score: float
    action: str
    confidence: float
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            'market': self.market,
            'last_price': self.last_price,
            'sma_fast': self.sma_fast,
            'sma_slow': self.sma_slow,
            'momentum_pct': self.momentum_pct,
            'volatility_pct': self.volatility_pct,
            'news_score': self.news_score,
            'score': self.score,
            'action': self.action,
            'confidence': self.confidence,
            'reason': self.reason,
        }


class AiTradingBot:
    def __init__(self, coinex: CoinExClient, markets: list[str]) -> None:
        self.coinex = coinex
        self.markets = markets

    def get_or_create_state(self, db: Session) -> BotState:
        state = db.get(BotState, 1)
        if state is None:
            state = BotState(id=1)
            db.add(state)
            db.commit()
            db.refresh(state)
        return state

    def update_state(self, db: Session, **kwargs: Any) -> BotState:
        state = self.get_or_create_state(db)
        for key, value in kwargs.items():
            if value is not None and hasattr(state, key):
                setattr(state, key, value)
        db.add(state)
        db.commit()
        db.refresh(state)
        return state

    async def analyze_market(self, db: Session, market: str) -> IndicatorPack:
        market = market.upper()
        raw = await self.coinex.get_kline(market, period='1min', limit=120)
        candles = self._parse_candles(raw)
        closes = [c['close'] for c in candles]
        if len(closes) < 20:
            raise ValueError(f'not enough candles for {market}')

        last_price = closes[-1]
        sma_fast = statistics.fmean(closes[-9:])
        sma_slow = statistics.fmean(closes[-30:]) if len(closes) >= 30 else statistics.fmean(closes)
        momentum_pct = ((last_price - closes[-10]) / closes[-10]) * 100 if closes[-10] else 0.0
        returns = [((closes[i] - closes[i - 1]) / closes[i - 1]) * 100 for i in range(1, len(closes)) if closes[i - 1]]
        volatility_pct = statistics.pstdev(returns[-30:]) if len(returns) >= 2 else 0.0
        news_score = self._latest_news_score(db, market)

        trend_bonus = 18 if sma_fast > sma_slow else -12
        momentum_bonus = max(-20, min(20, momentum_pct * 4))
        news_bonus = (news_score - 50) * 0.35
        volatility_penalty = min(18, volatility_pct * 1.8)
        score = max(0, min(100, 50 + trend_bonus + momentum_bonus + news_bonus - volatility_penalty))

        if score >= 70:
            action = 'buy'
        elif score <= 35:
            action = 'sell'
        else:
            action = 'hold'

        confidence = max(0, min(100, abs(score - 50) * 1.8))
        reason = (
            f'{market}: score {score:.1f}. '
            f'Быстрая средняя {sma_fast:.8f}, медленная {sma_slow:.8f}; '
            f'импульс {momentum_pct:.2f}%, волатильность {volatility_pct:.2f}%, новостной фон {news_score:.1f}. '
            f'Действие: {action}.'
        )
        return IndicatorPack(
            market=market,
            last_price=last_price,
            sma_fast=sma_fast,
            sma_slow=sma_slow,
            momentum_pct=momentum_pct,
            volatility_pct=volatility_pct,
            news_score=news_score,
            score=score,
            action=action,
            confidence=confidence,
            reason=reason,
        )

    async def choose_best_market(self, db: Session) -> IndicatorPack:
        packs: list[IndicatorPack] = []
        for market in self.markets:
            try:
                packs.append(await self.analyze_market(db, market))
            except Exception:
                continue
        if not packs:
            raise ValueError('no market could be analyzed')
        return max(packs, key=lambda item: item.score)

    async def make_decision(self, db: Session, market: str | None = None, persist: bool = True) -> AiDecision:
        pack = await self.analyze_market(db, market) if market else await self.choose_best_market(db)
        decision = AiDecision(
            market=pack.market,
            action=pack.action,
            score=pack.score,
            confidence=pack.confidence,
            reason=pack.reason,
            indicators_json=json.dumps(pack.as_dict(), ensure_ascii=False),
            executed=False,
        )
        if persist:
            db.add(decision)
            db.commit()
            db.refresh(decision)
        return decision

    def risk_check(self, db: Session, decision: AiDecision, quote_amount: float) -> dict[str, Any]:
        state = self.get_or_create_state(db)
        open_positions = db.query(DemoPosition).filter(DemoPosition.is_open.is_(True), DemoPosition.amount > 0).count()
        reasons: list[str] = []

        if state.emergency_stop:
            reasons.append('emergency stop is active')
        if not state.enabled:
            reasons.append('bot is disabled')
        if decision.score < state.min_signal_score and decision.action == 'buy':
            reasons.append('signal score below minimum')
        if quote_amount > state.max_quote_per_trade:
            reasons.append('quote amount exceeds max per trade')
        if open_positions >= state.max_open_positions and decision.action == 'buy':
            reasons.append('max open positions reached')
        if decision.action == 'hold':
            reasons.append('decision is hold')

        return {
            'allowed': not reasons,
            'reasons': reasons,
            'state': self.state_to_dict(state),
        }

    def record_manual_signal(self, db: Session, title: str, market: str, sentiment: str, score: float, source: str = 'manual', url: str = '') -> NewsSignal:
        signal = NewsSignal(
            title=title,
            market=market.upper(),
            sentiment=sentiment.lower(),
            score=max(0, min(100, score)),
            source=source,
            url=url,
        )
        db.add(signal)
        db.commit()
        db.refresh(signal)
        return signal

    def recent_decisions(self, db: Session, limit: int = 50) -> list[AiDecision]:
        return db.query(AiDecision).order_by(AiDecision.id.desc()).limit(limit).all()

    def recent_signals(self, db: Session, limit: int = 50) -> list[NewsSignal]:
        return db.query(NewsSignal).order_by(NewsSignal.id.desc()).limit(limit).all()

    def state_to_dict(self, state: BotState) -> dict[str, Any]:
        return {
            'enabled': state.enabled,
            'trade_mode': state.trade_mode,
            'trade_style_mode': state.trade_style_mode,
            'min_signal_score': state.min_signal_score,
            'max_open_positions': state.max_open_positions,
            'max_quote_per_trade': state.max_quote_per_trade,
            'emergency_stop': state.emergency_stop,
        }

    def _parse_candles(self, raw: dict[str, Any]) -> list[dict[str, float]]:
        rows = raw.get('data') or []
        candles: list[dict[str, float]] = []
        for row in rows:
            if isinstance(row, dict):
                close = row.get('close') or row.get('closing_price')
                open_ = row.get('open') or row.get('opening_price')
                high = row.get('high') or row.get('highest_price')
                low = row.get('low') or row.get('lowest_price')
                created_at = row.get('created_at') or row.get('time') or 0
            else:
                created_at, open_, close, high, low = row[0], row[1], row[2], row[3], row[4]
            try:
                candles.append({
                    'time': float(created_at),
                    'open': float(open_),
                    'high': float(high),
                    'low': float(low),
                    'close': float(close),
                })
            except (TypeError, ValueError, IndexError):
                continue
        candles.sort(key=lambda item: item['time'])
        return candles

    def _latest_news_score(self, db: Session, market: str) -> float:
        signals = db.query(NewsSignal).filter(NewsSignal.market == market).order_by(NewsSignal.id.desc()).limit(10).all()
        if not signals:
            return 50.0
        return statistics.fmean(signal.score for signal in signals)


def decision_to_dict(decision: AiDecision) -> dict[str, Any]:
    return {
        'id': decision.id,
        'market': decision.market,
        'action': decision.action,
        'score': decision.score,
        'confidence': decision.confidence,
        'reason': decision.reason,
        'indicators': json.loads(decision.indicators_json or '{}'),
        'executed': decision.executed,
        'created_at': decision.created_at.isoformat(),
    }


def signal_to_dict(signal: NewsSignal) -> dict[str, Any]:
    return {
        'id': signal.id,
        'source': signal.source,
        'title': signal.title,
        'market': signal.market,
        'sentiment': signal.sentiment,
        'score': signal.score,
        'url': signal.url,
        'created_at': signal.created_at.isoformat(),
    }


def trade_marker_from_record(trade: DemoTradeRecord) -> dict[str, Any]:
    return {
        'id': trade.id,
        'time': int(trade.created_at.timestamp()),
        'market': trade.market,
        'side': trade.side,
        'price': trade.price,
        'amount': trade.amount,
        'text': f'{trade.side.upper()} {trade.amount:g} @ {trade.price:g}',
    }
