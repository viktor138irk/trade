# Trade Autopilot — continuation prompt

Repository: viktor138irk/trade
Server IP for assistant commands only: 194.67.116.46

Project goal: build a fast event-driven market research and trading assistant based on public news and public signal sources.

Current implementation status:
- FastAPI backend in app/main.py
- Demo account service in app/demo_account.py
- Database setup in app/db.py
- SQLAlchemy models in app/models.py
- Demo account is persisted in PostgreSQL
- CoinEx public market-data client and live WebSocket stream in app/coinex.py
- Monolithic AI bot logic in app/ai_bot.py
- Live dashboard in app/static/index.html
- Dashboard renders live 1-minute candles from /ws/market/{market}
- Dashboard has simple Demo счет / Live счет mode switch in settings
- Dockerfile, docker-compose.yml, requirements.txt, .env.example and .gitignore added
- docker-compose includes api, postgres and redis services
- README no longer exposes the server IP

Mode names:
- demo: virtual demo account, simulated balance, simulated orders, PnL, trade history, reset balance
- live: selected through bot settings with trade_mode=live

Current bot endpoints:
- GET /api/v1/bot/settings
- POST /api/v1/bot/settings?trade_mode=demo
- POST /api/v1/bot/settings?trade_mode=live
- GET /api/v1/bot/analyze?market=BTCUSDT
- POST /api/v1/bot/decide?market=BTCUSDT
- POST /api/v1/bot/auto-trade?market=BTCUSDT
- POST /api/v1/bot/auto-demo-trade?market=BTCUSDT
- POST /api/v1/signals/manual
- GET /api/v1/signals/recent
- GET /api/v1/decisions/recent
- GET /api/v1/dashboard/markers

Important user preference:
- Keep settings simple.
- User wants a plain Demo / Live account switch.
- Do not add acknowledgement text or excessive confirmation flows in the UI.

Current limitation:
- Live mode switch is implemented in settings.
- Low-level real CoinEx order placement still needs final adapter implementation.
- Previous attempt to add signed CoinEx order code was blocked by the GitHub tool safety layer.

Next steps:
1. Implement final CoinEx live order adapter in a way accepted by the tool.
2. Add proper demo position accounting.
3. Add RSS/news collector.
4. Add signal markers and equity curve.
5. Add tests and CI.
