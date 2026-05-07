import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
import websockets


class CoinExClient:
    def __init__(self, api_base: str) -> None:
        self.api_base = api_base.rstrip('/')

    async def get_market_list(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f'{self.api_base}/spot/market')
            response.raise_for_status()
            return response.json()

    async def get_market_info(self, market: str | None = None) -> dict[str, Any]:
        params = {'market': market.upper()} if market else None
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f'{self.api_base}/spot/market', params=params)
            response.raise_for_status()
            return response.json()

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

    def extract_price_from_ticker(self, ticker: dict[str, Any]) -> float | None:
        data = ticker.get('data')
        if isinstance(data, list) and data:
            data = data[0]
        if not isinstance(data, dict):
            return None
        price_raw = data.get('last') or data.get('close') or data.get('last_price')
        try:
            return float(price_raw)
        except (TypeError, ValueError):
            return None


class CoinExLiveStream:
    def __init__(self, ws_url: str, rest_client: CoinExClient) -> None:
        self.ws_url = ws_url
        self.rest_client = rest_client

    async def trades(self, market: str) -> AsyncIterator[dict[str, Any]]:
        market = market.upper()
        try:
            async for event in self._trades_from_ws(market):
                yield event
        except Exception as exc:  # noqa: BLE001 - dashboard must keep breathing
            yield {
                'type': 'stream_warning',
                'market': market,
                'message': f'CoinEx WebSocket unavailable, using HTTP fallback: {exc}',
            }
            async for event in self._trades_from_http_fallback(market):
                yield event

    async def _trades_from_ws(self, market: str) -> AsyncIterator[dict[str, Any]]:
        subscribe_message = {
            'id': int(time.time()),
            'method': 'deals.subscribe',
            'params': {
                'market_list': [market],
            },
        }
        async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=20) as websocket:
            await websocket.send(json.dumps(subscribe_message))
            async for raw_message in websocket:
                message = json.loads(raw_message)
                if message.get('method') == 'server.ping':
                    await websocket.send(json.dumps({'id': message.get('id'), 'method': 'server.pong', 'params': {}}))
                    continue
                normalized = self._normalize_deals_message(market, message)
                if normalized is not None:
                    yield normalized

    async def _trades_from_http_fallback(self, market: str) -> AsyncIterator[dict[str, Any]]:
        while True:
            ticker = await self.rest_client.get_ticker(market)
            price = self.rest_client.extract_price_from_ticker(ticker)
            if price is not None:
                yield {
                    'type': 'live_price',
                    'source': 'coinex_http_fallback',
                    'market': market,
                    'price': price,
                    'ts': int(time.time() * 1000),
                    'raw': ticker,
                }
            await asyncio.sleep(2)

    def _normalize_deals_message(self, market: str, message: dict[str, Any]) -> dict[str, Any] | None:
        params = message.get('params')
        if not params:
            return None

        deals: list[Any] = []
        if isinstance(params, dict):
            if params.get('market') and params.get('market') != market:
                return None
            deals = params.get('deal_list') or params.get('deals') or []
        elif isinstance(params, list):
            for item in params:
                if isinstance(item, dict):
                    deals.extend(item.get('deal_list') or item.get('deals') or [item])

        prices: list[float] = []
        for deal in deals:
            if not isinstance(deal, dict):
                continue
            price_raw = deal.get('price') or deal.get('deal_price')
            try:
                prices.append(float(price_raw))
            except (TypeError, ValueError):
                continue

        if not prices:
            return None

        return {
            'type': 'live_price',
            'source': 'coinex_ws',
            'market': market,
            'price': prices[-1],
            'ts': int(time.time() * 1000),
            'raw': message,
        }
