# Trade Autopilot

Сервис для анализа открытых новостей и рыночных данных с демо-счетом, CoinEx market data, AI-ботом и live-графиками.

## Режимы

- `demo` — режим по умолчанию. Виртуальный баланс, виртуальные сделки, история и PnL.
- `live` — режим работы с live-счетом. Переключается в настройках бота.

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
curl -X POST "http://localhost:8000/api/v1/bot/auto-trade?market=BTCUSDT"
```

Manual signal:

```bash
curl -X POST "http://localhost:8000/api/v1/signals/manual?title=BTC bullish news&market=BTCUSDT&sentiment=positive&score=80"
```

## Переключение Demo / Live

Через API:

```bash
curl -X POST "http://localhost:8000/api/v1/bot/settings?trade_mode=demo"
curl -X POST "http://localhost:8000/api/v1/bot/settings?trade_mode=live"
```

Через dashboard:

```text
Настройки -> Demo счет / Live счет
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
