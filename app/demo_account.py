from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.models import DemoAccountState, DemoPosition, DemoTradeRecord


class DemoTrade(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market: str
    side: str
    price: float
    amount: float
    quote_amount: float
    reason: str
    created_at: datetime


class DemoAccount(BaseModel):
    quote_asset: str
    balance: float
    equity: float
    realized_pnl: float = 0.0
    trades: list[DemoTrade] = Field(default_factory=list)


class DemoAccountService:
    def __init__(self, initial_balance: float, quote_asset: str) -> None:
        self.initial_balance = initial_balance
        self.quote_asset = quote_asset

    def _get_or_create_state(self, db: Session) -> DemoAccountState:
        state = db.get(DemoAccountState, 1)
        if state is None:
            state = DemoAccountState(id=1, quote_asset=self.quote_asset, balance=self.initial_balance, equity=self.initial_balance, realized_pnl=0.0)
            db.add(state)
            db.commit()
            db.refresh(state)
        return state

    def snapshot(self, db: Session) -> DemoAccount:
        state = self._get_or_create_state(db)
        trades = db.query(DemoTradeRecord).order_by(DemoTradeRecord.id.desc()).limit(100).all()
        return DemoAccount(
            quote_asset=state.quote_asset,
            balance=state.balance,
            equity=state.equity,
            realized_pnl=state.realized_pnl,
            trades=[DemoTrade.model_validate(trade) for trade in reversed(trades)],
        )

    def reset(self, db: Session) -> DemoAccount:
        db.query(DemoTradeRecord).delete()
        db.query(DemoPosition).delete()
        state = self._get_or_create_state(db)
        state.quote_asset = self.quote_asset
        state.balance = self.initial_balance
        state.equity = self.initial_balance
        state.realized_pnl = 0.0
        db.add(state)
        db.commit()
        db.refresh(state)
        return self.snapshot(db)

    def add_demo_trade(self, db: Session, market: str, side: str, price: float, amount: float, reason: str, allow_position_add: bool = False) -> DemoTrade:
        if price <= 0 or amount <= 0:
            raise ValueError('price and amount must be positive')

        market = market.upper()
        quote_amount = price * amount
        side_normalized = side.lower()
        if side_normalized not in {'buy', 'sell'}:
            raise ValueError('side must be buy or sell')

        state = self._get_or_create_state(db)
        position = self.get_open_position(db, market)

        if side_normalized == 'buy':
            if position is not None and not allow_position_add:
                raise ValueError(f'по {market} уже есть открытая сделка: правило один market = одна сделка')
            if quote_amount > state.balance:
                raise ValueError('not enough demo balance')
            state.balance -= quote_amount
            if position is None:
                position = DemoPosition(
                    market=market,
                    side='long',
                    amount=amount,
                    avg_entry_price=price,
                    current_price=price,
                    take_profit=price * 1.02,
                    stop_loss=price * 0.99,
                    unrealized_pnl=0.0,
                    unrealized_pnl_pct=0.0,
                    is_open=True,
                )
                db.add(position)
            else:
                total_cost = position.avg_entry_price * position.amount + quote_amount
                position.amount += amount
                position.avg_entry_price = total_cost / position.amount
                position.current_price = price
                position.take_profit = position.avg_entry_price * 1.02
                position.stop_loss = position.avg_entry_price * 0.99
        else:
            if position is not None and position.amount > 0:
                sell_amount = min(amount, position.amount)
                quote_amount = price * sell_amount
                state.balance += quote_amount
                realized = (price - position.avg_entry_price) * sell_amount
                position.amount -= sell_amount
                position.current_price = price
                position.realized_pnl += realized
                state.realized_pnl += realized
                amount = sell_amount
                if position.amount <= 1e-12:
                    position.amount = 0.0
                    position.is_open = False
                    position.closed_at = datetime.now(timezone.utc)
            else:
                raise ValueError(f'нет открытой позиции по {market} для закрытия')

        self.reprice_positions(db, {market: price})
        state.equity = state.balance + self.open_positions_value(db)
        trade = DemoTradeRecord(market=market, side=side_normalized, price=price, amount=amount, quote_amount=price * amount, reason=reason)
        db.add(state)
        db.add(trade)
        db.commit()
        db.refresh(trade)
        return DemoTrade.model_validate(trade)

    def close_full_market(self, db: Session, market: str, price: float, reason: str) -> DemoTrade:
        position = self.get_open_position(db, market)
        if position is None or position.amount <= 0:
            raise ValueError(f'нет открытой позиции по {market} для полного закрытия')
        # In demo mode the database position is the balance source of truth.
        # In live mode the execution adapter must replace this with exchange balance verification.
        verified_amount = position.amount
        return self.add_demo_trade(db, market, 'sell', price, verified_amount, f'{reason}; закрытие всей доступной суммы {verified_amount:g}')

    def get_open_position(self, db: Session, market: str) -> DemoPosition | None:
        return db.query(DemoPosition).filter(DemoPosition.market == market.upper(), DemoPosition.is_open.is_(True)).first()

    def has_open_position(self, db: Session, market: str) -> bool:
        return self.get_open_position(db, market) is not None

    def reprice_positions(self, db: Session, prices: dict[str, float]) -> None:
        for market, price in prices.items():
            position = db.query(DemoPosition).filter(DemoPosition.market == market.upper(), DemoPosition.is_open.is_(True)).first()
            if position is None or price <= 0:
                continue
            position.current_price = price
            position.unrealized_pnl = (price - position.avg_entry_price) * position.amount
            base = position.avg_entry_price * position.amount
            position.unrealized_pnl_pct = (position.unrealized_pnl / base * 100) if base else 0.0
            db.add(position)

    def open_positions_value(self, db: Session) -> float:
        positions = db.query(DemoPosition).filter(DemoPosition.is_open.is_(True)).all()
        return sum(position.current_price * position.amount for position in positions)
