from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.ai_bot import AiTradingBot, decision_to_dict, signal_to_dict, trade_marker_from_record
from app.coinex import CoinExClient, CoinExLiveStream
from app.core import get_settings
from app.db import SessionLocal, get_db, init_db
from app.demo_account import DemoAccountService
from app.models import DemoTradeRecord

settings = get_settings()
coinex = CoinExClient(settings.coinex_api_base)
live_stream = CoinExLiveStream(settings.coinex_ws_spot, coinex)
demo_service = DemoAccountService(settings.demo_initial_balance, settings.demo_quote_asset)
ai_bot = AiTradingBot(coinex, settings.markets)

app = FastAPI(title=settings.app_name)
static_dir = Path(__file__).parent / 'static'
app.mount('/static', StaticFiles(directory=static_dir), name='static')


@app.on_event('startup')
def on_startup() -> None:
    init_db()


@app.get('/')
async def dashboard() -> FileResponse:
    return FileResponse(static_dir / 'index.html')


@app.get('/health')
async def health() -> dict:
    return {
        'status': 'ok',
        'app': settings.app_name,
        'env': settings.app_env,
        'default_market': settings.default_market,
    }


@app.get('/api/v1/demo/account')
async def demo_account(db: Session = Depends(get_db)) -> dict:
    return demo_service.snapshot(db).model_dump(mode='json')


@app.post('/api/v1/demo/reset')
async def reset_demo_account(db: Session = Depends(get_db)) -> dict:
    return demo_service.reset(db).model_dump(mode='json')


@app.post('/api/v1/demo/trades')
async def create_demo_trade(
    market: str,
    side: str,
    price: float,
    amount: float,
    reason: str = 'manual demo trade',
    db: Session = Depends(get_db),
) -> dict:
    try:
        trade = demo_service.add_demo_trade(db=db, market=market, side=side, price=price, amount=amount, reason=reason)
        return trade.model_dump(mode='json')
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/api/v1/market/kline')
async def market_kline(market: str | None = None, period: str = '1min', limit: int = 100) -> dict:
    return await coinex.get_kline(market or settings.default_market, period, limit)


@app.get('/api/v1/market/ticker')
async def market_ticker(market: str | None = None) -> dict:
    return await coinex.get_ticker(market or settings.default_market)


@app.get('/api/v1/bot/settings')
async def bot_settings(db: Session = Depends(get_db)) -> dict:
    state = ai_bot.get_or_create_state(db)
    data = ai_bot.state_to_dict(state)
    data['markets'] = settings.markets
    return data


@app.post('/api/v1/bot/settings')
async def update_bot_settings(
    enabled: bool | None = None,
    trade_mode: str | None = None,
    trade_style_mode: str | None = None,
    min_signal_score: float | None = None,
    max_open_positions: int | None = None,
    max_quote_per_trade: float | None = None,
    emergency_stop: bool | None = None,
    db: Session = Depends(get_db),
) -> dict:
    if trade_mode is not None and trade_mode not in {'demo', 'live'}:
        raise HTTPException(status_code=400, detail='trade_mode must be demo or live')
    state = ai_bot.update_state(
        db,
        enabled=enabled,
        trade_mode=trade_mode,
        trade_style_mode=trade_style_mode,
        min_signal_score=min_signal_score,
        max_open_positions=max_open_positions,
        max_quote_per_trade=max_quote_per_trade,
        emergency_stop=emergency_stop,
    )
    return ai_bot.state_to_dict(state)


@app.post('/api/v1/bot/live/enable')
async def enable_live_mode(db: Session = Depends(get_db)) -> dict:
    state = ai_bot.update_state(db, trade_mode='live', emergency_stop=False)
    return {'trade_mode': 'live', 'settings': ai_bot.state_to_dict(state)}


@app.post('/api/v1/bot/live/disable')
async def disable_live_mode(db: Session = Depends(get_db)) -> dict:
    state = ai_bot.update_state(db, trade_mode='demo')
    return {'trade_mode': 'demo', 'settings': ai_bot.state_to_dict(state)}


@app.get('/api/v1/bot/analyze')
async def analyze_market(market: str | None = None, db: Session = Depends(get_db)) -> dict:
    try:
        pack = await ai_bot.analyze_market(db, market or settings.default_market)
        return pack.as_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post('/api/v1/bot/decide')
async def bot_decide(market: str | None = None, db: Session = Depends(get_db)) -> dict:
    try:
        decision = await ai_bot.make_decision(db, market)
        return decision_to_dict(decision)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _force_demo_trade(db: Session, decision) -> dict:
    state = ai_bot.get_or_create_state(db)
    decision_data = decision_to_dict(decision)
    price = float(decision_data['indicators']['last_price'])
    side = decision.action if decision.action in {'buy', 'sell'} else 'buy'
    amount = max(1.0, state.max_quote_per_trade) / price
    trade = demo_service.add_demo_trade(db, decision.market, side, price, amount, decision.reason)
    decision.executed = True
    db.add(decision)
    db.commit()
    return {
        'executed': True,
        'mode': 'demo',
        'decision': decision_to_dict(decision),
        'trade': trade.model_dump(mode='json'),
    }


@app.post('/api/v1/bot/auto-demo-trade')
async def auto_demo_trade(market: str | None = None, db: Session = Depends(get_db)) -> dict:
    try:
        decision = await ai_bot.make_decision(db, market)
        return _force_demo_trade(db, decision)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post('/api/v1/bot/auto-trade')
async def auto_trade(market: str | None = None, db: Session = Depends(get_db)) -> dict:
    state = ai_bot.get_or_create_state(db)
    decision = await ai_bot.make_decision(db, market)
    if state.trade_mode == 'live':
        return {
            'executed': False,
            'mode': 'live',
            'decision': decision_to_dict(decision),
            'message': 'Live mode is selected. Real CoinEx execution adapter is not connected yet; demo execution is stable.',
        }
    return _force_demo_trade(db, decision)


@app.post('/api/v1/signals/manual')
async def create_manual_signal(
    title: str,
    market: str,
    sentiment: str = 'neutral',
    score: float = 50.0,
    source: str = 'manual',
    url: str = '',
    db: Session = Depends(get_db),
) -> dict:
    signal = ai_bot.record_manual_signal(db, title=title, market=market, sentiment=sentiment, score=score, source=source, url=url)
    return signal_to_dict(signal)


@app.get('/api/v1/signals/recent')
async def recent_signals(limit: int = 50, db: Session = Depends(get_db)) -> dict:
    return {'items': [signal_to_dict(item) for item in ai_bot.recent_signals(db, limit)]}


@app.get('/api/v1/decisions/recent')
async def recent_decisions(limit: int = 50, db: Session = Depends(get_db)) -> dict:
    return {'items': [decision_to_dict(item) for item in ai_bot.recent_decisions(db, limit)]}


@app.get('/api/v1/dashboard/markers')
async def dashboard_markers(market: str | None = None, limit: int = 100, db: Session = Depends(get_db)) -> dict:
    query = db.query(DemoTradeRecord)
    if market:
        query = query.filter(DemoTradeRecord.market == market.upper())
    trades = query.order_by(DemoTradeRecord.id.desc()).limit(limit).all()
    return {'items': [trade_marker_from_record(item) for item in reversed(trades)]}


@app.websocket('/ws/market/{market}')
async def market_stream(websocket: WebSocket, market: str) -> None:
    await websocket.accept()
    try:
        async for live_event in live_stream.trades(market):
            with SessionLocal() as db:
                account = demo_service.snapshot(db).model_dump(mode='json')
                state = ai_bot.state_to_dict(ai_bot.get_or_create_state(db))
            live_event['demo_account'] = account
            live_event['bot_state'] = state
            await websocket.send_json(live_event)
    except WebSocketDisconnect:
        return
