# Trade Autopilot

Сервис для анализа открытых новостей и рыночных данных с демо-счетом, CoinEx market data и live-графиками.

## Режимы

- `demo` — режим по умолчанию. Виртуальный баланс, виртуальные сделки, история и PnL.
- `live` — защищенный режим для будущего подключения биржевого исполнения. По умолчанию выключен.

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

## Сервер

Основной сервер проекта: `194.67.116.46`

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

## Структура

```text
app/
  api/          HTTP routes
  core/         settings
  exchanges/   CoinEx market-data client
  services/    demo account and business logic
  static/      live dashboard
  main.py      FastAPI entrypoint
```

## Важно

Проект стартует с демо-счета. Реальное исполнение должно проходить через отдельный защищенный адаптер, риск-лимиты и аварийную остановку.
