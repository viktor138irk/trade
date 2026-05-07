from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.ai_bot import AiTradingBot
from app.core import Settings
from app.models import AiDecision


@dataclass
class ExecutionResult:
    executed: bool
    mode: str
    message: str
    payload: dict[str, Any]


class LiveExecutionGuard:
    def __init__(self, settings: Settings, ai_bot: AiTradingBot) -> None:
        self.settings = settings
        self.ai_bot = ai_bot

    def assert_live_ready(self, db: Session) -> dict[str, Any]:
        state = self.ai_bot.get_or_create_state(db)
        problems: list[str] = []

        if state.trade_mode != 'live':
            problems.append('bot state trade_mode is not live')
        if not state.live_acknowledged:
            problems.append('live trading risk acknowledgement is missing')
        if state.emergency_stop:
            problems.append('emergency stop is active')
        if not self.settings.enable_live_trading or self.settings.trade_mode != 'live':
            problems.append('environment live flags are not enabled')
        if not self.settings.coinex_credentials_present:
            problems.append('CoinEx credentials are missing')

        return {
            'ready': not problems,
            'problems': problems,
            'state': self.ai_bot.state_to_dict(state),
            'env_live_enabled': self.settings.live_enabled,
            'coinex_credentials_present': self.settings.coinex_credentials_present,
        }

    def execute_guarded_live_order(self, db: Session, decision: AiDecision, quote_amount: float) -> ExecutionResult:
        readiness = self.assert_live_ready(db)
        risk = self.ai_bot.risk_check(db, decision, quote_amount)

        if not readiness['ready']:
            return ExecutionResult(
                executed=False,
                mode='live_guard_blocked',
                message='Live execution is not ready',
                payload={'readiness': readiness, 'risk': risk},
            )

        if not risk['allowed']:
            return ExecutionResult(
                executed=False,
                mode='live_risk_blocked',
                message='Risk engine blocked live execution',
                payload={'readiness': readiness, 'risk': risk},
            )

        return ExecutionResult(
            executed=False,
            mode='live_adapter_pending',
            message='Live guard passed. Low-level CoinEx order adapter is intentionally separated for final verification.',
            payload={'readiness': readiness, 'risk': risk, 'decision_id': decision.id},
        )
