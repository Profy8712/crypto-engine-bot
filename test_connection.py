import os, ccxt
from dotenv import load_dotenv

def get_exchange():
    load_dotenv()
    exchange_id = os.getenv("EXCHANGE", "bybit")
    ex = getattr(ccxt, exchange_id)({
        "apiKey": os.getenv("API_KEY"),
        "secret": os.getenv("API_SECRET"),
        "enableRateLimit": True,
        "options": { "defaultType": "swap", "defaultSettle": "USDT" },
    })
    if hasattr(ex, "set_sandbox_mode"):
        ex.set_sandbox_mode(os.getenv("TESTNET", "true").lower() == "true")
    ex.load_markets()
    return ex

def normalize_to_swap(ex, symbol):
    if symbol in ex.markets and ex.market(symbol).get("type") in ("swap", "future"):
        return symbol
    candidate = symbol if ":" in symbol else f"{symbol}/USDT:USDT" if "/" not in symbol else f"{symbol}:USDT"
    if candidate in ex.markets: return candidate
    raise ValueError("Set SYMBOL like BTC/USDT:USDT")

def main():
    ex = get_exchange()
    symbol = normalize_to_swap(ex, os.getenv("SYMBOL", "BTC/USDT:USDT"))
    t = ex.fetch_ticker(symbol)
    env = "testnet" if os.getenv("TESTNET","true").lower()=="true" else "prod"
    print(f"✅ {ex.id} {env} | {symbol} last: {t['last']}")

if __name__ == "__main__":
    main()
