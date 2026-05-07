from typing import Any
import httpx


class CoinExClient:
    def __init__(self, api_base: str) -> None:
        self.api_base = api_base.rstrip('/')

    async def get_kline(self, market: str, period: str = '1min', limit: int = 100) -> dict[str, Any]:
        params = {
            'market': market.upper(),
            'period': period,
            'limit': max(1, min(limit, 1000)),
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f'{self.api_base}/spot/kline', params=params)
            response.raise_for_status()
            return response.json()

    async def get_ticker(self, market: str) -> dict[str, Any]:
        params = {'market': market.upper()}
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f'{self.api_base}/spot/ticker', params=params)
            response.raise_for_status()
            return response.json()
