# Trade Autopilot — continuation prompt

Repository: viktor138irk/trade
Server IP: 194.67.116.46

Project goal: build a fast event-driven market research and trading assistant based on public news and public signal sources.

Current implementation status:
- FastAPI backend added in app/main.py
- Demo account service added in app/demo_account.py
- Database setup added in app/db.py
- SQLAlchemy models added in app/models.py
- Demo account is now persisted in PostgreSQL
- CoinEx public market-data client and live WebSocket stream added in app/coinex.py
- Live dashboard added in app/static/index.html
- Dashboard now renders live 1-minute candles from /ws/market/{market}
- Dockerfile, docker-compose.yml, requirements.txt, .env.example and .gitignore added
- docker-compose includes api, postgres and redis services
- README includes local/server startup and live chart notes

Default mode: demo mode. Demo mode uses a virtual demo account and simulated orders. Live trading can be enabled only explicitly with environment variables and API credentials.

Mode names:
- demo: virtual demo account, simulated balance, simulated orders, PnL, trade history, reset balance
- live: future real exchange execution, disabled by default and protected by explicit flags

Demo account implementation:
- Initial virtual balance configurable by DEMO_INITIAL_BALANCE, default 10000 USDT
- PostgreSQL tables:
  - demo_account_state
  - demo_trades
- Endpoints:
  - GET /api/v1/demo/account
  - POST /api/v1/demo/reset
  - POST /api/v1/demo/trades
- Current limitation: position accounting is basic and needs proper inventory/average-entry logic

CoinEx market-data implementation:
- HTTP base URL: https://api.coinex.com/v2
- Spot WebSocket base URL: wss://socket.coinex.com/v2/spot
- Current endpoints:
  - GET /api/v1/market/kline
  - GET /api/v1/market/ticker
  - WS /ws/market/{market}
- WebSocket endpoint now uses CoinEx deals.subscribe live stream
- If CoinEx WebSocket fails, backend falls back to HTTP ticker polling

Live charts implementation:
- Dashboard is served at /
- Uses TradingView Lightweight Charts from CDN
- Historical candles load from CoinEx HTTP kline
- Current 1-minute candle updates from backend live_price events
- Dashboard shows live price, source, latest stream event, demo balance and equity
- Next: add trade markers, signal markers and equity curve

Exchange integration plan:
- CoinEx adapter for market data, account status and guarded order placement
- Live trading flag: TRADE_MODE=demo|live
- CoinEx credentials must be stored only in environment variables
- Live mode must require ENABLE_LIVE_TRADING=true plus TRADE_MODE=live
- Add risk checks before every live order
- Add emergency stop flag to block all new live orders

Planned MVP modules:
- collector: RSS/news/public signal ingestion
- normalizer: cleaning, deduplication, timestamps, source score
- signal_engine: asset detection, market mapping, sentiment, confidence
- pair_selector: choose candidate market using news relevance, liquidity, spread, volatility and session time
- strategy_engine: create trade decision with explanation
- risk_engine: max loss per day, max position size, stop-loss, take-profit, cooldown, emergency stop flag
- execution: demo execution by default, CoinEx live execution only when explicitly enabled
- monitoring: logs, metrics, health checks
- dashboard: live charts, current market, signals, trades, demo account, risk state

Preferred stack:
- Python 3.12+
- FastAPI
- PostgreSQL
- Redis
- Docker Compose
- GitHub Actions
- Lightweight frontend dashboard using React or server-rendered page with TradingView Lightweight Charts

Development rules:
- Start with demo mode and backtests
- Live trading is opt-in only
- Keep secrets out of git. Use .env and server env vars
- Every major change must update this file
- Every strategy must log the reason for each decision
- Keep changes small and reviewable

Next steps:
1. Add tests and CI
2. Add proper demo position accounting
3. Verify CoinEx WS payload in production logs and adjust parser if needed
4. Add trade markers on dashboard
5. Add first RSS/news collector
6. Add risk config and emergency stop
7. Add guarded CoinEx live execution adapter
