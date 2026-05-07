import asyncio
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.ai_bot import AiTradingBot, decision_to_dict, signal_to_dict, trade_marker_from_record
from app.auth import require_auth
from app.coinex import CoinExClient, CoinExLiveStream
from app.core import get_settings
from app.db import SessionLocal, get_db, init_db
from app.demo_account import DemoAccountService
from app.legacy_bot import LegacyBotService
from app.models import DemoTradeRecord
from app.monitor import SignalMonitor

settings = get_settings()
coinex = CoinExClient(settings.coinex_api_base)
live_stream = CoinExLiveStream(settings.coinex_ws_spot, coinex)
demo_service = DemoAccountService(settings.demo_initial_balance, settings.demo_quote_asset)
ai_bot = AiTradingBot(coinex, settings.markets)
legacy_bot = LegacyBotService()
monitor = SignalMonitor(ai_bot, demo_service, legacy_bot)
monitor_task: asyncio.Task | None = None

app = FastAPI(title=settings.app_name)
static_dir = Path(__file__).parent / 'static'
app.mount('/static', StaticFiles(directory=static_dir), name='static')


def ensure_monitor_running() -> None:
    global monitor_task
    if monitor_task is None or monitor_task.done():
        monitor_task = asyncio.create_task(monitor.loop(SessionLocal, interval_seconds=10))


@app.on_event('startup')
async def on_startup() -> None:
    init_db()
    with SessionLocal() as db:
        legacy_bot.ensure_defaults(db)
        state = ai_bot.get_or_create_state(db)
        if state.enabled:
            ensure_monitor_running()


@app.get('/')
async def dashboard(_: str = Depends(require_auth)) -> FileResponse:
    return FileResponse(static_dir / 'index.html')


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok', 'app': settings.app_name, 'env': settings.app_env, 'default_market': settings.default_market}


@app.get('/api/v1/app/bootstrap')
async def app_bootstrap(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    state = ai_bot.get_or_create_state(db)
    account = demo_service.snapshot(db)
    legacy_bot.ensure_defaults(db)
    return {'app': settings.app_name, 'default_market': settings.default_market, 'markets': settings.markets, 'bot': ai_bot.state_to_dict(state), 'account': account.model_dump(mode='json'), 'legacy': legacy_bot.dashboard(db), 'monitor': monitor.status()}


@app.get('/api/v1/demo/account')
async def demo_account(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    return demo_service.snapshot(db).model_dump(mode='json')


@app.post('/api/v1/demo/reset')
async def reset_demo_account(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    return demo_service.reset(db).model_dump(mode='json')


@app.post('/api/v1/demo/trades')
async def create_demo_trade(market: str, side: str, price: float, amount: float, reason: str = 'manual demo trade', _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    try:
        trade = demo_service.add_demo_trade(db=db, market=market, side=side, price=price, amount=amount, reason=reason)
        legacy_bot.snapshot_history(db)
        return trade.model_dump(mode='json')
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/api/v1/market/kline')
async def market_kline(market: str | None = None, period: str = '1min', limit: int = 100, _: str = Depends(require_auth)) -> dict:
    return await coinex.get_kline(market or settings.default_market, period, limit)


@app.get('/api/v1/market/ticker')
async def market_ticker(market: str | None = None, _: str = Depends(require_auth)) -> dict:
    return await coinex.get_ticker(market or settings.default_market)


@app.get('/api/v1/bot/settings')
async def bot_settings(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    state = ai_bot.get_or_create_state(db)
    data = ai_bot.state_to_dict(state)
    data['markets'] = settings.markets
    return data


@app.post('/api/v1/bot/settings')
async def update_bot_settings(enabled: bool | None = None, trade_mode: str | None = None, trade_style_mode: str | None = None, min_signal_score: float | None = None, max_open_positions: int | None = None, max_quote_per_trade: float | None = None, emergency_stop: bool | None = None, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    if trade_mode is not None and trade_mode not in {'demo', 'live'}:
        raise HTTPException(status_code=400, detail='trade_mode must be demo or live')
    state = ai_bot.update_state(db, enabled=enabled, trade_mode=trade_mode, trade_style_mode=trade_style_mode, min_signal_score=min_signal_score, max_open_positions=max_open_positions, max_quote_per_trade=max_quote_per_trade, emergency_stop=emergency_stop)
    if state.enabled:
        ensure_monitor_running()
    return ai_bot.state_to_dict(state)


@app.get('/api/v1/monitor/status')
async def monitor_status(_: str = Depends(require_auth)) -> dict:
    return monitor.status()


@app.get('/api/v1/monitor/logs')
async def monitor_logs(limit: int = 80, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    return {'items': monitor.recent_logs(db, limit)}


@app.post('/api/v1/monitor/start')
async def monitor_start(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    state = ai_bot.update_state(db, enabled=True)
    ensure_monitor_running()
    data = monitor.status()
    data['bot'] = ai_bot.state_to_dict(state)
    return data


@app.post('/api/v1/monitor/stop')
async def monitor_stop(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    state = ai_bot.update_state(db, enabled=False)
    monitor.stop()
    data = monitor.status()
    data['bot'] = ai_bot.state_to_dict(state)
    return data


@app.post('/api/v1/bot/live/enable')
async def enable_live_mode(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    state = ai_bot.update_state(db, trade_mode='live', emergency_stop=False)
    return {'trade_mode': 'live', 'settings': ai_bot.state_to_dict(state)}


@app.post('/api/v1/bot/live/disable')
async def disable_live_mode(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    state = ai_bot.update_state(db, trade_mode='demo')
    return {'trade_mode': 'demo', 'settings': ai_bot.state_to_dict(state)}


@app.get('/api/v1/bot/analyze')
async def analyze_market(market: str | None = None, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    try:
        pack = await ai_bot.analyze_market(db, market or settings.default_market)
        return pack.as_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/api/v1/bot/best-market')
async def best_market(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    try:
        pack = await ai_bot.choose_best_market(db)
        return pack.as_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post('/api/v1/bot/decide')
async def bot_decide(market: str | None = None, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
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
    legacy_bot.snapshot_history(db)
    monitor.write_log(db, 'success', 'manual_auto_order', f'Открыта сделка вручную: {trade.side.upper()} {trade.market}, сумма {trade.quote_amount:.2f} USDT, цена {trade.price:.8f}.', market=trade.market, action=trade.side, score=decision.score)
    return {'executed': True, 'mode': 'demo', 'decision': decision_to_dict(decision), 'trade': trade.model_dump(mode='json')}


@app.post('/api/v1/bot/auto-demo-trade')
async def auto_demo_trade(market: str | None = None, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    try:
        decision = await ai_bot.make_decision(db, market)
        return _force_demo_trade(db, decision)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post('/api/v1/bot/auto-trade')
async def auto_trade(market: str | None = None, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    state = ai_bot.get_or_create_state(db)
    decision = await ai_bot.make_decision(db, market)
    if state.trade_mode == 'live':
        monitor.write_log(db, 'warning', 'live_order_pending', f'Live-режим включен. Сигнал {decision.market} найден, но CoinEx live adapter еще не подключен.', market=decision.market, action=decision.action, score=decision.score)
        return {'executed': False, 'mode': 'live', 'decision': decision_to_dict(decision), 'message': 'Live mode is selected. CoinEx execution adapter is the next implementation step.'}
    return _force_demo_trade(db, decision)


@app.post('/api/v1/signals/manual')
async def create_manual_signal(title: str, market: str, sentiment: str = 'neutral', score: float = 50.0, source: str = 'manual', url: str = '', _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    signal = ai_bot.record_manual_signal(db, title=title, market=market, sentiment=sentiment, score=score, source=source, url=url)
    return signal_to_dict(signal)


@app.get('/api/v1/signals/recent')
async def recent_signals(limit: int = 50, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    return {'items': [signal_to_dict(item) for item in ai_bot.recent_signals(db, limit)]}


@app.get('/api/v1/decisions/recent')
async def recent_decisions(limit: int = 50, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    return {'items': [decision_to_dict(item) for item in ai_bot.recent_decisions(db, limit)]}


@app.get('/api/v1/dashboard/markers')
async def dashboard_markers(market: str | None = None, limit: int = 100, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    query = db.query(DemoTradeRecord)
    if market:
        query = query.filter(DemoTradeRecord.market == market.upper())
    trades = query.order_by(DemoTradeRecord.id.desc()).limit(limit).all()
    return {'items': [trade_marker_from_record(item) for item in reversed(trades)]}


@app.get('/api/v1/legacy/dashboard')
async def legacy_dashboard(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    return legacy_bot.dashboard(db)


@app.get('/api/v1/legacy/open-trades')
async def legacy_open_trades(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    return {'items': legacy_bot.open_positions(db)}


@app.get('/api/v1/legacy/closed-trades')
async def legacy_closed_trades(limit: int = 50, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    return {'items': legacy_bot.closed_positions(db, limit)}


@app.get('/api/v1/legacy/chart-history')
async def legacy_chart_history(limit: int = 100, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    return {'items': legacy_bot.chart_history(db, limit)}


@app.get('/api/v1/legacy/strategies')
async def legacy_strategies(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    legacy_bot.ensure_defaults(db)
    return {'items': legacy_bot.dashboard(db)['strategies']}


@app.post('/api/v1/legacy/strategies/{strategy_id}')
async def legacy_update_strategy(strategy_id: int, enabled: bool | None = None, dry_run: bool | None = None, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    try:
        return legacy_bot.update_strategy(db, strategy_id, enabled, dry_run)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get('/api/v1/legacy/coinex')
async def legacy_coinex(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    return legacy_bot.dashboard(db)['coinex']


@app.post('/api/v1/legacy/coinex')
async def legacy_update_coinex(enabled: bool | None = None, access_id: str | None = None, secret_key: str | None = None, mode: str | None = None, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    return legacy_bot.update_coinex(db, enabled, access_id, secret_key, mode)


@app.post('/api/v1/legacy/telegram')
async def legacy_update_telegram(enabled: bool | None = None, chat_id: str | None = None, message_format: str | None = None, _: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    return legacy_bot.update_telegram(db, enabled, chat_id, message_format)


@app.get('/api/v1/legacy/updater/status')
async def legacy_updater_status(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    return legacy_bot.updater_status(db)


@app.post('/api/v1/legacy/terminal')
async def legacy_terminal(command: str, _: str = Depends(require_auth)) -> dict:
    return legacy_bot.terminal_command(command)


@app.get('/api/v1/android/status')
async def android_status(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    return legacy_bot.android_status(db)


@app.websocket('/ws/market/{market}')
async def market_stream(websocket: WebSocket, market: str) -> None:
    await websocket.accept()
    try:
        async for live_event in live_stream.trades(market):
            with SessionLocal() as db:
                account = demo_service.snapshot(db).model_dump(mode='json')
                state = ai_bot.state_to_dict(ai_bot.get_or_create_state(db))
                price = live_event.get('price')
                if price:
                    demo_service.reprice_positions(db, {market: float(price)})
                    db.commit()
            live_event['demo_account'] = account
            live_event['bot_state'] = state
            await websocket.send_json(live_event)
    except WebSocketDisconnect:
        return
