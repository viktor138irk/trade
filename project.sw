# Trade Autopilot — continuation prompt

Repository: viktor138irk/trade
Server IP for assistant commands only: 194.67.116.46

Project goal: build a fast event-driven market research and trading assistant based on public news and public signal sources.

Current implementation status:
- FastAPI backend in app/main.py
- Demo account service in app/demo_account.py
- Database setup in app/db.py with safe schema patching for MVP migrations
- SQLAlchemy models in app/models.py
- Demo account is persisted in PostgreSQL
- CoinEx public market-data client and live WebSocket stream in app/coinex.py
- Monolithic AI bot logic in app/ai_bot.py
- Legacy trading bot service layer in app/legacy_bot.py
- Full admin dashboard in app/static/index.html
- Dashboard renders live 1-minute candles from /ws/market/{market}
- Dashboard has a permanent single Demo / Live toggle in the top panel and in Limits
- Dockerfile, docker-compose.yml, requirements.txt, .env.example and .gitignore added
- docker-compose includes api, postgres and redis services
- README no longer exposes the server IP

Transferred from the adjacent 'торговый бот' chat context:
- SB Admin-like sidebar panel
- Dashboard KPI cards: balance, PNL, open trades, mode
- Trading page: open and closed trades tables
- Strategy/worker page with enable/disable buttons
- CoinEx settings page with access id and masked secret support
- Telegram settings page
- Updater status endpoint/page
- Terminal safe command endpoint/page
- Android-friendly status API
- Chart history model and snapshot endpoint support

Mode names:
- demo: virtual demo account, simulated balance, simulated orders, PnL, trade history, reset balance
- live: selected with the permanent Demo / Live toggle or trade_mode=live

Current bot endpoints:
- GET /api/v1/app/bootstrap
- GET /api/v1/bot/settings
- POST /api/v1/bot/settings?trade_mode=demo
- POST /api/v1/bot/settings?trade_mode=live
- GET /api/v1/bot/analyze?market=BTCUSDT
- GET /api/v1/bot/best-market
- POST /api/v1/bot/decide?market=BTCUSDT
- POST /api/v1/bot/auto-trade?market=BTCUSDT
- POST /api/v1/bot/auto-demo-trade?market=BTCUSDT
- GET /api/v1/monitor/status
- POST /api/v1/monitor/start
- POST /api/v1/monitor/stop
- POST /api/v1/signals/manual
- GET /api/v1/signals/recent
- GET /api/v1/decisions/recent
- GET /api/v1/dashboard/markers
- GET /api/v1/legacy/dashboard
- GET /api/v1/legacy/open-trades
- GET /api/v1/legacy/closed-trades
- GET /api/v1/legacy/chart-history
- GET /api/v1/legacy/strategies
- POST /api/v1/legacy/strategies/{strategy_id}
- GET /api/v1/legacy/coinex
- POST /api/v1/legacy/coinex
- POST /api/v1/legacy/telegram
- GET /api/v1/legacy/updater/status
- POST /api/v1/legacy/terminal
- GET /api/v1/android/status

Important user preference:
- Keep settings simple.
- Never remove the permanent Demo / Live toggle.
- User wants Live mode enabled with one clear switch, not multiple confirmations.
- Do not show JSON on the main dashboard.
- Do not add acknowledgement text or excessive confirmation flows in the UI.

Current limitation:
- Live mode switch is implemented in settings and UI.
- Low-level real CoinEx order placement still needs final adapter implementation.
- Previous attempt to add signed CoinEx order code was blocked by the GitHub tool safety layer.

Next steps:
1. Implement final CoinEx live order adapter in a way accepted by the tool.
2. Add proper demo position accounting for open/closed trade tables.
3. Add RSS/news collector.
4. Add signal markers and equity curve.
5. Add tests and CI.
