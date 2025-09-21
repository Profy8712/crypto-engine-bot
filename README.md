# Crypto Engine Bot

A Python trading engine for **Bybit Testnet** (demo environment).  
The bot connects to Bybit via [ccxt](https://github.com/ccxt/ccxt), opens trades from config, supports **DCA** and **dynamic take-profits**.  

This version includes **test scripts** to check your API keys and orders.  

---

## 🚀 Features
- Connects to **Bybit Testnet** with API keys
- `.env` configuration (safe, secrets not in git)
- `test_connection.py` → verify connection & fetch last price
- `test_order.py` → place & cancel a limit order
- Configurable trade size (`TEST_QTY` in `.env`)
- Extensible engine design

---

## 📂 Project structure
```
crypto-engine-bot/
├─ app/                 # core engine (in progress)
├─ test_connection.py   # test: check API keys and price
├─ test_order.py        # test: place and cancel limit order
├─ .env.example         # example env file (copy to .env)
├─ requirements.txt
├─ README.md
└─ .gitignore
```

---

## ⚙️ Configuration

### 1. Copy `.env.example` to `.env`
```bash
cp .env.example .env
```

### 2. Fill in your Bybit Testnet API keys
```env
EXCHANGE=bybit
API_KEY=your_bybit_testnet_key
API_SECRET=your_bybit_testnet_secret
TESTNET=true
SYMBOL=BTCUSDT

# optional: quantity for test_order.py
TEST_QTY=0.001
```

🔑 **API keys are created in Bybit Testnet → Profile → API Management → Create New Key**.  
- Select **System-generated API Key**  
- Permissions: **Read-Write** (Orders, Positions, Trade)  
- Environment: **Testnet**  
- ⚠️ Do NOT enable Withdrawal permissions  

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
Expected output:
```
✅ Connected to bybit (testnet)
📌 BTCUSDT last price: 65432.5
```

### 3. Test placing and canceling an order
```bash
python test_order.py
```
Expected output:
```
📌 Last: 65000.0, placing LIMIT buy 0.001 @ 61750.0
✅ Placed order: 1234567890
🔎 Open orders count: 1
🗑️  Canceled order: 1234567890
```

---

## 🧪 Next steps
- Expand engine logic (`app/engine.py`) with averaging (DCA) and take-profit (TP) logic  
- Add monitoring (console, REST API)  
- Docker support  

---

## ⚠️ Disclaimer
This project is for **educational purposes only**.  
It is designed to work in **Bybit Testnet**.  
Do **not** use with real funds unless you fully understand the risks of algorithmic trading.
