from datetime import datetime, timezone
from pydantic import BaseModel, Field


class DemoTrade(BaseModel):
    id: int
    market: str
    side: str
    price: float
    amount: float
    quote_amount: float
    reason: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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
        self.account = DemoAccount(
            quote_asset=quote_asset,
            balance=initial_balance,
            equity=initial_balance,
        )

    def snapshot(self) -> DemoAccount:
        return self.account

    def reset(self) -> DemoAccount:
        self.account = DemoAccount(
            quote_asset=self.quote_asset,
            balance=self.initial_balance,
            equity=self.initial_balance,
        )
        return self.account

    def add_demo_trade(self, market: str, side: str, price: float, amount: float, reason: str) -> DemoTrade:
        if price <= 0 or amount <= 0:
            raise ValueError('price and amount must be positive')

        quote_amount = price * amount
        side_normalized = side.lower()
        if side_normalized not in {'buy', 'sell'}:
            raise ValueError('side must be buy or sell')

        if side_normalized == 'buy':
            if quote_amount > self.account.balance:
                raise ValueError('not enough demo balance')
            self.account.balance -= quote_amount
        else:
            self.account.balance += quote_amount
            self.account.realized_pnl += quote_amount

        self.account.equity = self.account.balance
        trade = DemoTrade(
            id=len(self.account.trades) + 1,
            market=market.upper(),
            side=side_normalized,
            price=price,
            amount=amount,
            quote_amount=quote_amount,
            reason=reason,
        )
        self.account.trades.append(trade)
        return trade
