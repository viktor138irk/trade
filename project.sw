# Trade Autopilot — continuation prompt

Repository: viktor138irk/trade
Server IP: 194.67.116.46

Project goal: build a fast event-driven market research and trading assistant based on public news and public signal sources.

Default mode: demo mode. Demo mode uses a virtual demo account and simulated orders. Live trading can be enabled only explicitly with environment variables and API credentials.

Mode names:
- demo: virtual demo account, simulated balance, simulated orders, PnL, trade history, reset balance
- live: real CoinEx execution, disabled by default and protected by explicit flags

Demo account plan:
- Initial virtual balance configurable by DEMO_INITIAL_BALANCE, default 10000 USDT
- Store demo balances, positions, orders, fills and PnL in PostgreSQL
- Support reset demo account endpoint
- Show demo equity curve and trade markers on live charts
- Every demo trade must include a strategy reason and risk-check result

Exchange integration plan:
- CoinEx adapter for market data, account status and guarded order placement
- Live trading flag: TRADE_MODE=demo|live
- CoinEx credentials must be stored only in environment variables: COINEX_ACCESS_ID and COINEX_SECRET_KEY
- Live mode must require ENABLE_LIVE_TRADING=true plus TRADE_MODE=live
- Add risk checks before every live order
- Add emergency stop flag to block all new live orders

Live charts plan:
- FastAPI backend exposes REST endpoints for historical candles, signals and trades
- WebSocket endpoint streams live ticks/candles, detected news signals and execution events
- Frontend dashboard shows candlestick chart, selected pair, signal markers, demo/live trades, demo account balance and risk status

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
1. Create project skeleton
2. Add FastAPI health endpoint
3. Add docker-compose with PostgreSQL and Redis
4. Add CoinEx market-data client
5. Add demo account ledger
6. Add guarded CoinEx live execution adapter
7. Add live chart dashboard
8. Add risk config and emergency stop
