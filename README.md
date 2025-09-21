# Crypto Engine Bot

A Python trading engine for **Bybit** and **Gate.io** (testnet/demo).  
The bot opens trades from a JSON configuration, supports **DCA (averaging)** with limit orders, and places **dynamic take-profits (TP)** that automatically recalculate when the average entry price changes.

---

## 🚀 Features
- Connects to exchange (Bybit/Gate.io) via **ccxt** or native SDK
- Works in **testnet/demo** mode (safe environment)
- Opens trades based on JSON config
- Supports **DCA (Dollar-Cost Averaging)** via limit orders
- Automatically recalculates and **replaces TP orders** on average price change
- Monitoring through console logs (REST API optional bonus)
- Configurable via `.env` and `config.json`
- Extensible architecture (easy to add other exchanges)

---

## 🛠 Tech stack
- Python 3.8+
- [ccxt](https://github.com/ccxt/ccxt) (unified exchange client)
- [pydantic](https://docs.pydantic.dev/) (config validation)
- [python-dotenv](https://github.com/theskumar/python-dotenv) (env management)
- FastAPI + Uvicorn (optional REST monitoring)
- Docker (bonus)

---

## 📂 Project structure
```
crypto-engine-bot/
├─ app/
│  ├─ main.py                # entry point
│  ├─ engine.py              # trade engine logic
│  ├─ models.py              # Pydantic config models
│  ├─ exchanges/             # exchange clients
│  │   ├─ base.py
│  │   └─ ccxt_client.py
│  └─ config/
│      └─ config.example.json
├─ .env.example
├─ requirements.txt
├─ README.md
└─ .gitignore
```

---

## ⚙️ Configuration

### `.env` file (copy from `.env.example`):
```env
EXCHANGE=bybit
API_KEY=your_api_key
API_SECRET=your_api_secret
TESTNET=true
SYMBOL=BTCUSDT
```

### Example `config.json`
```json
{
  "symbol": "BTCUSDT",
  "side": "buy",
  "base_order_qty": 0.001,
  "leverage": 3,
  "margin_mode": "isolated",
  "entry": { "type": "market" },
  "dca": {
    "enabled": true,
    "levels": [
      { "price_offset_pct": -0.5, "qty": 0.001 },
      { "price_offset_pct": -1.0, "qty": 0.0015 }
    ],
    "replace_on_fill": true
  },
  "take_profits": {
    "levels": [
      { "tp_pct": 0.3, "qty_pct": 30 },
      { "tp_pct": 0.8, "qty_pct": 70 }
    ],
    "from_average_price": true,
    "replace_on_reavg": true
  },
  "risk": {
    "max_active_orders": 10,
    "max_position_qty": 0.01
  }
}
```

---

## ▶️ Run

### 1. Clone repository
```bash
git clone https://github.com/<your-username>/crypto-engine-bot.git
cd crypto-engine-bot
```

### 2. Create virtual environment & install dependencies
```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
.venv\Scripts\activate      # Windows PowerShell

pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Copy config and set environment
```bash
cp .env.example .env
# edit .env and add your testnet API keys
```

### 4. Run bot
```bash
python app/main.py
```

---

## 🧪 Example output
```
✅ Engine boot OK. BTCUSDT last price = 65000.12
📌 Opening buy BTCUSDT qty=0.001
✅ Market order placed: {...}
```

---

## 📌 Roadmap
- [ ] Add real-time monitoring via REST API (FastAPI)
- [ ] Add Docker support
- [ ] Add logging to file and trade history tracking
- [ ] Add Web UI with live charts

---

## ⚠️ Disclaimer
This bot is for **educational and demo purposes only**.  
It is designed to work in **testnet/demo** environments.  
Do **not** use real money unless you understand the risks of algorithmic trading.
