# Crypto Engine Bot

Trading engine for **Bybit Testnet** written in Python.  
It connects to Bybit via [ccxt](https://github.com/ccxt/ccxt), opens trades from a JSON config, supports **averaging (DCA)** and **dynamic take-profits (TP)**.

---

## 🚀 Features
- Connects to **Bybit Testnet** using API keys
- `.env` configuration (safe, excluded from git)
- Open trades from a JSON config
- Market and limit entry
- Averaging (DCA) via limit orders
- Dynamic take-profit (TP) recalculation when average entry price changes
- Monitoring open positions and orders
- ✅ Test scripts included (`test_connection.py`, `test_order.py`, `close_position.py`)

### Bonus (optional)
- Dockerfile for containerized run
- Async implementation
- REST API (FastAPI) for manual control and monitoring
- Logging to file
- Possible UI monitoring with charts for entry/exit points

---

## 📂 Project structure
```
crypto-engine-bot/
├── app/
│   ├── __init__.py
│   ├── main.py           # main entrypoint
│   ├── engine.py         # engine logic
│   └── exchanges/
│       ├── __init__.py
│       ├── base.py
│       └── ccxt_client.py
├── test_connection.py     # check API and last price
├── test_order.py          # place & cancel test order
├── close_position.py      # close open position
├── config.example.json    # example trade config
├── .env.example           # example env file
├── requirements.txt
├── Dockerfile             # (bonus)
├── README.md
└── logs/                  # (optional logs)
```

---

## ⚙️ Configuration

### 1. Copy `.env.example` → `.env`
```bash
cp .env.example .env
```

### 2. Fill in your Bybit Testnet API keys
```env
EXCHANGE=bybit
API_KEY=your_api_key
API_SECRET=your_api_secret
TESTNET=true
SYMBOL=BTCUSDT
TEST_QTY=0.0001
```

📌 Keys are created in **Bybit Testnet → API Management → Create New Key**.  
- Type: System-generated API Key  
- Permissions: Orders, Positions, Trade  
- Environment: Testnet  
- ⚠️ Do not enable withdrawal permissions!  

### 3. Example config (`config.example.json`)
```json
{
  "symbol": "BTCUSDT",
  "side": "buy",
  "base_order_qty": 0.0001,
  "entry": { "type": "market" },
  "dca_orders": [
    { "price": 110000, "qty": 0.0001 },
    { "price": 105000, "qty": 0.0001 }
  ],
  "tp_orders": [
    { "percent": 1.0, "qty_percent": 50 },
    { "percent": 2.0, "qty_percent": 50 }
  ]
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
📌 BTCUSDT last price: 118272.7
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

## 🐳 Docker (bonus)
```bash
docker build -t crypto-engine-bot .
docker run --env-file .env crypto-engine-bot
```

---

## 📊 Monitoring (bonus)
- REST API with FastAPI (for manual control & monitoring)  
- Basic logging to `logs/engine.log`  
- Optional: simple web UI with chart marking entry/exit points  

---

## 📸 Demo
- `test_connection.py` → connected to Bybit  
- `test_order.py` → limit order placed and canceled  
- `python -m app.main` → market order opened  
- Bybit Testnet screenshots: order in **Trade History / Positions**  

---

## ⚠️ Disclaimer
This bot is for **educational purposes only**.  
It is designed for **Bybit Testnet**.  
Do not use with real funds unless you fully understand the risks of algorithmic trading.
