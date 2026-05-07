# Trade Autopilot

Сервис для анализа открытых новостей и рыночных данных с демо-счетом, CoinEx market data, AI-ботом и live-графиками.

## Режимы

- `demo` — режим по умолчанию. Виртуальный баланс, виртуальные сделки, история и PnL.
- `live` — защищенный режим для подключения биржевого исполнения. По умолчанию выключен и требует явного подтверждения риска.

## Быстрый старт

```bash
cp .env.example .env
docker compose up --build
```

API:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/demo/account
curl "http://localhost:8000/api/v1/market/kline?market=BTCUSDT&period=1min&limit=100"
```

Dashboard:

```text
http://localhost:8000/
```

Live-график:

- История свечей грузится через CoinEx HTTP kline.
- Текущая свеча обновляется через backend WebSocket `/ws/market/{market}`.
- Backend подключается к CoinEx spot WebSocket и подписывается на сделки.
- Если WebSocket CoinEx недоступен, включается HTTP fallback.

## AI-бот

Endpoints:

```bash
curl http://localhost:8000/api/v1/bot/settings
curl "http://localhost:8000/api/v1/bot/analyze?market=BTCUSDT"
curl -X POST "http://localhost:8000/api/v1/bot/decide?market=BTCUSDT"
curl -X POST "http://localhost:8000/api/v1/bot/auto-demo-trade?market=BTCUSDT"
```

Manual signal:

```bash
curl -X POST "http://localhost:8000/api/v1/signals/manual?title=BTC bullish news&market=BTCUSDT&sentiment=positive&score=80"
```

## Live mode guard

Live mode requires all of these:

```env
TRADE_MODE=live
ENABLE_LIVE_TRADING=true
COINEX_ACCESS_ID=...
COINEX_SECRET_KEY=...
```

Then enable through API with acknowledgement:

```bash
curl -X POST "http://localhost:8000/api/v1/bot/live/enable?ack=I_UNDERSTAND_LIVE_TRADING_RISK"
```

Disable live mode:

```bash
curl -X POST http://localhost:8000/api/v1/bot/live/disable
```

## Установка Git на сервер

Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y git ca-certificates curl

git --version
```

Клонирование:

```bash
cd /opt
sudo git clone https://github.com/viktor138irk/trade.git trade
sudo chown -R $USER:$USER /opt/trade
cd /opt/trade
```

## Docker на сервере

```bash
sudo apt update
sudo apt install -y git curl ca-certificates docker.io docker-compose-plugin
sudo systemctl enable --now docker

cd /opt/trade
cp .env.example .env
docker compose up -d --build
```

## Обновление на сервере

```bash
cd /opt/trade
git pull
docker compose down
docker compose up -d --build
```

## Структура

```text
app/
  ai_bot.py      monolithic AI bot logic
  coinex.py      CoinEx HTTP client and live WebSocket stream
  core.py        settings
  db.py          database setup
  demo_account.py demo account service
  models.py      SQLAlchemy models
  static/        live dashboard
  main.py        FastAPI entrypoint
```

## Важно

Проект стартует с демо-счета. Реальное исполнение должно проходить через защищенный live guard, риск-лимиты и аварийную остановку.
