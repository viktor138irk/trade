from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'Trade Autopilot'
    app_env: str = 'local'
    trade_mode: str = 'demo'
    enable_live_trading: bool = False
    demo_initial_balance: float = 10000.0
    demo_quote_asset: str = 'USDT'
    coinex_api_base: str = 'https://api.coinex.com/v2'
    coinex_ws_spot: str = 'wss://socket.coinex.com/v2/spot'
    default_market: str = 'BTCUSDT'
    database_url: str = 'sqlite:///./trade.db'
    redis_url: str = 'redis://localhost:6379/0'

    @property
    def live_enabled(self) -> bool:
        return self.trade_mode == 'live' and self.enable_live_trading


@lru_cache
def get_settings() -> Settings:
    return Settings()
