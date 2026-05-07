from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.models import DemoAccountState, DemoTradeRecord


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
            state = DemoAccountState(
                id=1,
                quote_asset=self.quote_asset,
                balance=self.initial_balance,
                equity=self.initial_balance,
                realized_pnl=0.0,
            )
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
        state = self._get_or_create_state(db)
        state.quote_asset = self.quote_asset
        state.balance = self.initial_balance
        state.equity = self.initial_balance
        state.realized_pnl = 0.0
        db.add(state)
        db.commit()
        db.refresh(state)
        return self.snapshot(db)

    def add_demo_trade(self, db: Session, market: str, side: str, price: float, amount: float, reason: str) -> DemoTrade:
        if price <= 0 or amount <= 0:
            raise ValueError('price and amount must be positive')

        quote_amount = price * amount
        side_normalized = side.lower()
        if side_normalized not in {'buy', 'sell'}:
            raise ValueError('side must be buy or sell')

        state = self._get_or_create_state(db)

        if side_normalized == 'buy':
            if quote_amount > state.balance:
                raise ValueError('not enough demo balance')
            state.balance -= quote_amount
        else:
            state.balance += quote_amount
            state.realized_pnl += quote_amount

        state.equity = state.balance
        trade = DemoTradeRecord(
            market=market.upper(),
            side=side_normalized,
            price=price,
            amount=amount,
            quote_amount=quote_amount,
            reason=reason,
        )
        db.add(state)
        db.add(trade)
        db.commit()
        db.refresh(trade)
        return DemoTrade.model_validate(trade)
