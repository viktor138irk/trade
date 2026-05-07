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
- CoinEx public ticker can request all markets.
- CoinEx market info sync methods added to app/coinex.py
- CoinEx market rules service added in app/market_rules.py
- Monolithic AI bot logic in app/ai_bot.py
- Legacy trading bot service layer in app/legacy_bot.py
- Full admin dashboard in app/static/index.html
- Dashboard renders live 1-minute candles from /ws/market/{market}
- Dashboard has a permanent single Demo / Live toggle in the top panel and in Limits
- Dockerfile, docker-compose.yml, requirements.txt, .env.example and .gitignore added
- docker-compose includes api, postgres and redis services
- README no longer exposes the server IP
- scripts/fix_monitor_start.py added to patch monitor stop/start restart race on server.

Trading rules now implemented:
- Bot syncs CoinEx public market rules: min amount, min quote amount, amount precision, price precision, maker/taker fee placeholders.
- Market rules are stored in table market_rules.
- Endpoint POST /api/v1/market/rules/sync manually syncs rules.
- Endpoint GET /api/v1/market/rules lists stored rules.
- Manual sync now requests all active USDT markets from CoinEx, not only MARKET_UNIVERSE.
- Monitor automatically attempts CoinEx rules sync on first run.
- After sync, monitor replaces ai_bot.markets with all active USDT markets stored in market_rules.
- One market = one open trade: duplicate open position on same market is blocked.
- Bot rotates markets and skips markets with open positions, so it does not get stuck on one market.
- For sell/close in demo, bot closes the full available market position amount from DB.
- Demo equity and PNL include open positions: total_pnl = realized_pnl + unrealized_pnl.
- Dashboard KPI service returns balance, equity, realized_pnl, unrealized_pnl, total_pnl, open_positions_value.
- Live account placeholder exists at GET /api/v1/live/account but real signed balance/order adapter is still pending.

Mode names:
- demo: virtual demo account, simulated balance, simulated orders, PnL, trade history, reset balance
- live: selected with the permanent Demo / Live toggle or trade_mode=live

Important user preference:
- Keep settings simple.
- Never remove the permanent Demo / Live toggle.
- User wants Live mode enabled with one clear switch, not multiple confirmations.
- Do not show JSON on the main dashboard.
- Do not add acknowledgement text or excessive confirmation flows in the UI.
- One market must have only one open trade at a time.
- Bot must not get stuck on one market.
- Closing must use the full available amount for that market; in live mode verify through CoinEx API first.
- Live mode should eventually execute buy/sell just like demo when signal passes score, after balance verification.

Known monitor issue and patch:
- If monitor was stopped and started quickly, old async task could remain alive but sleeping while monitor.running was false, so a new monitor task was not created.
- Apply patch after git pull on server: python3 scripts/fix_monitor_start.py
- Then rebuild: docker compose down && docker compose up -d --build

Current limitation:
- Live mode switch is implemented in settings and UI.
- Live signal detection works, but low-level real CoinEx order placement still needs final adapter implementation.
- Attempts to commit signed CoinEx order/balance code and ccxt live broker were blocked by the GitHub tool safety layer.
- Official CoinEx docs confirm signed endpoints are required: GET /assets/spot/balance for balances and POST /spot/order for orders.

Next steps:
1. Implement final CoinEx live order adapter with balance verification before sell/close, using an allowed approach.
2. Surface live balance/equity when the signed balance adapter is available.
3. Surface market rules sync status in dashboard UI.
4. Add RSS/news collector.
5. Add signal markers and equity curve.
6. Add tests and CI.
