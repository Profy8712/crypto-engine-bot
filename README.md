# Crypto Engine Bot

Trading engine for **Bybit Testnet** written in Python.  
It connects to Bybit via [ccxt](https://github.com/ccxt/ccxt), opens trades from a JSON config, supports **DCA averaging**, **dynamic take-profits (TP)** and basic **SL/trailing SL** logic.  
Also includes **FastAPI monitoring API** and **Web UI with charts and events**.

---

## 🚀 Features
- Connects to **Bybit Testnet** using API keys  
- Configurable via `.env` + JSON deal config  
- Market or limit entry  
- DCA (averaging) grid with recalculation of average entry price  
- Dynamic TP recalculation when average price changes  
- Stop Loss (SL) and Trailing SL  
- Move SL to breakeven after first TP  
- Monitoring of positions and orders via REST API  
- ✅ Web UI with charts, markers (ENTRY, GRID, TP, SL, BE) and tables  

### Bonus
- Dockerfile for containerized run  
- Logging to both console and `logs/engine.log`  
- Event storage in SQLite (`logs/events.db`)  

---

## 📂 Project structure
```
crypto-engine-bot/
├── app/
│   ├── engine.py           # core trading engine
│   ├── api.py              # REST API (FastAPI + Web UI)
│   ├── db.py               # SQLite events storage
│   ├── event_bus.py        # async pub/sub bus for events
│   ├── models.py           # deal config schema
│   ├── exchanges/
│   │   └── ccxt_client.py  # ccxt wrapper
│   └── utils/logger.py     # logger setup
├── scripts/
│   ├── run_deal.py         # run engine with deal config
│   ├── fake_events.py      # generate fake events for UI demo
│   └── patch_engine_events.py # auto-insert emit_event calls
├── static/monitor.html     # Web UI monitoring page
├── config.example.json      # example trade config
├── .env.example             # example environment file
├── test_connection.py       # check API & last price
├── test_order.py            # place & cancel order
├── close_position.py        # close open position
├── requirements.txt
├── Dockerfile
└── logs/                    # engine logs + events.db
```

---

## ⚙️ Configuration

### 1. Environment (`.env`)
Copy `.env.example` → `.env` and fill in your keys:
```env
EXCHANGE=bybit
API_KEY=your_api_key
API_SECRET=your_api_secret
TESTNET=true
SYMBOL=BTC/USDT:USDT
LOG_LEVEL=INFO
```

📌 Create keys in **Bybit Testnet → API Management → Create New Key**.  
- Permissions: Orders, Positions, Trade  
- Environment: Testnet  
- ⚠️ Do not enable withdrawals!  

---

### 2. Example config (`config.example.json`)
```json
{
  "account": "Bybit/Testnet",
  "symbol": "BTC/USDT:USDT",
  "side": "short",
  "market_order_amount": 2000,
  "stop_loss_percent": 7,
  "trailing_sl_offset_percent": 3,
  "limit_orders_amount": 2000,
  "leverage": 10,
  "move_sl_to_breakeven": true,
  "tp_orders": [
    { "price_percent": 2.0, "quantity_percent": 25.0 },
    { "price_percent": 5.0, "quantity_percent": 25.0 },
    { "price_percent": 7.0, "quantity_percent": 25.0 },
    { "price_percent": 3.0, "quantity_percent": 25.0 }
  ],
  "limit_orders": {
    "range_percent": 5.0,
    "orders_count": 6,
    "engine_deal_duration_minutes": 110
  }
}
```

---

## ▶️ Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Test connection
```bash
python test_connection.py
```
Expected:
```
✅ Connected to bybit (testnet)
📌 BTC/USDT:USDT last price: 118272.7
```

### 3. Test placing & canceling an order
```bash
python test_order.py
```

### 4. Run engine with config
```bash
python scripts/run_deal.py config.example.json
```

### 5. Generate fake events (for UI demo)
```bash
python scripts/fake_events.py
```

### 6. Close position
```bash
python close_position.py
```

---

## 🌐 REST API + Web UI

Run API:
```bash
uvicorn app.api:app --reload --host 0.0.0.0 --port 8000
```

### Endpoints
- `GET /ping` → health check (`{"status": "ok"}`)  
- `GET /status?symbol=BTC/USDT:USDT` → current positions and open orders  
- `GET /ticker?symbol=BTC/USDT:USDT` → last market price  
- `GET /events?symbol=BTC/USDT:USDT` → recent trade events  
- `GET /ohlcv?symbol=BTC/USDT:USDT&timeframe=1m` → OHLCV candles  

### Web UI
Open in browser:  
```
http://127.0.0.1:8000/monitor?symbol=BTC/USDT:USDT
```

### Swagger UI
Open in browser:  
```
http://127.0.0.1:8000/docs
```

---

## 📸 Screenshots
1. `01_engine_start.png` → logs when starting engine  
2. `02_bybit_positions.png` → open position in Positions tab  
3. `03_trade_history.png` → executed trades in Trade History  
4. `04_active_orders.png` → grid & TP orders in Active Orders  
5. `05_sl_trailing.png` → SL to breakeven or SL hit logs  
6. `06_config_file.png` → config.example.json in editor  
7. `07_docker_ps.png` → `docker ps` with running container  
8. `08_ui_monitoring.png` → Web UI monitoring with chart, markers and orders table  

![UI Monitoring Demo](docs/08_ui_monitoring.png)

---

## 🐳 Docker (optional)
Build:
```bash
docker build -t crypto-engine-bot .
```

Run:
```bash
docker run --env-file .env -p 8000:8000 crypto-engine-bot
```

---

## 📦 GitHub
Repository: [Profy8712/crypto-engine-bot](https://github.com/Profy8712/crypto-engine-bot)

---

## ⚠️ Disclaimer
This bot is for **educational purposes only**.  
It is designed for **Bybit Testnet**.  
Do not use with real funds unless you fully understand the risks of algorithmic trading.
