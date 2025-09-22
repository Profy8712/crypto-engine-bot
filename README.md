# Crypto Engine Bot

Trading engine for **Bybit Testnet** written in Python.  
It connects to Bybit via [ccxt](https://github.com/ccxt/ccxt), opens trades from a JSON config, supports **DCA averaging**, **dynamic take-profits (TP)** and basic **SL/trailing SL** logic.

---

## 🚀 Features
- Connects to **Bybit Testnet** using API keys  
- Configurable via `.env` + JSON deal config  
- Market or limit entry  
- DCA (averaging) grid with recalculation of average entry price  
- Dynamic TP recalculation when average price changes  
- Stop Loss (SL) and Trailing SL  
- Move SL to breakeven after first TP  
- Monitoring of positions and orders  
- ✅ Test scripts included (`test_connection.py`, `test_order.py`, `close_position.py`)  

### Bonus (optional)
- Dockerfile for containerized run  
- Logging to both console and `logs/engine.log`  
- REST API with FastAPI for monitoring  
- UI monitoring (future idea, with charts marking entry/exit)  

---

## 📂 Project structure
```
crypto-engine-bot/
├── app/
│   ├── __init__.py
│   ├── main.py            # entrypoint
│   ├── engine.py          # engine logic
│   ├── models.py          # config schema
│   ├── api.py             # REST API (FastAPI)
│   ├── utils/
│   │   └── logger.py      # logger setup
│   └── exchanges/
│       ├── __init__.py
│       ├── base.py        # abstract base class
│       └── ccxt_client.py # ccxt wrapper
├── config.example.json     # example trade config
├── .env.example            # example environment file
├── test_connection.py      # check API & last price
├── test_order.py           # place & cancel order
├── close_position.py       # close open position
├── requirements.txt
├── Dockerfile              # (bonus)
├── README.md
└── logs/                   # engine logs
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
TEST_QTY=0.001
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
python -m app.main
```

### 5. Close position
```bash
python close_position.py
```

---

## 🌐 REST API (monitoring)

You can also run the FastAPI server to monitor positions/orders:

### Run API
```bash
uvicorn app.api:app --reload --host 0.0.0.0 --port 8000
```

### Endpoints
- `GET /ping` → health check (`{"status": "ok"}`)  
- `GET /status?symbol=BTC/USDT:USDT` → current positions and open orders  
- `GET /ticker?symbol=BTC/USDT:USDT` → last market price  

### Swagger UI
Open in browser:  
```
http://127.0.0.1:8000/docs
```

---

## 🐳 Docker (bonus)
Build:
```bash
docker build -t crypto-engine-bot .
```

Run:
```bash
docker run --env-file .env -p 8000:8000 crypto-engine-bot
```

Check logs:
```bash
docker logs -f crypto-engine
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
8. `08_chart_with_entries.png` → chart with Entry, TP, Grid levels (optional)  

---

## 📦 GitHub
Repository: [Profy8712/crypto-engine-bot](https://github.com/Profy8712/crypto-engine-bot)

---

## ⚠️ Disclaimer
This bot is for **educational purposes only**.  
It is designed for **Bybit Testnet**.  
Do not use with real funds unless you fully understand the risks of algorithmic trading.
