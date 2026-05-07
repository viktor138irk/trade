import asyncio
from pathlib import Path
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.coinex import CoinExClient
from app.core import get_settings
from app.demo_account import DemoAccountService

settings = get_settings()
coinex = CoinExClient(settings.coinex_api_base)
demo_service = DemoAccountService(settings.demo_initial_balance, settings.demo_quote_asset)

app = FastAPI(title=settings.app_name)
static_dir = Path(__file__).parent / 'static'
app.mount('/static', StaticFiles(directory=static_dir), name='static')


@app.get('/')
async def dashboard() -> FileResponse:
    return FileResponse(static_dir / 'index.html')


@app.get('/health')
async def health() -> dict:
    return {
        'status': 'ok',
        'app': settings.app_name,
        'env': settings.app_env,
        'trade_mode': settings.trade_mode,
        'live_enabled': settings.live_enabled,
        'default_market': settings.default_market,
    }


@app.get('/api/v1/demo/account')
async def demo_account() -> dict:
    return demo_service.snapshot().model_dump(mode='json')


@app.post('/api/v1/demo/reset')
async def reset_demo_account() -> dict:
    return demo_service.reset().model_dump(mode='json')


@app.post('/api/v1/demo/trades')
async def create_demo_trade(market: str, side: str, price: float, amount: float, reason: str = 'manual demo trade') -> dict:
    try:
        trade = demo_service.add_demo_trade(market=market, side=side, price=price, amount=amount, reason=reason)
        return trade.model_dump(mode='json')
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/api/v1/market/kline')
async def market_kline(market: str | None = None, period: str = '1min', limit: int = 100) -> dict:
    return await coinex.get_kline(market or settings.default_market, period, limit)


@app.get('/api/v1/market/ticker')
async def market_ticker(market: str | None = None) -> dict:
    return await coinex.get_ticker(market or settings.default_market)


@app.websocket('/ws/market/{market}')
async def market_stream(websocket: WebSocket, market: str) -> None:
    await websocket.accept()
    try:
        while True:
            ticker = await coinex.get_ticker(market)
            await websocket.send_json({
                'type': 'ticker',
                'market': market.upper(),
                'data': ticker,
                'demo_account': demo_service.snapshot().model_dump(mode='json'),
            })
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        return
