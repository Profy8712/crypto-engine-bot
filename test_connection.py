import os
import ccxt
from dotenv import load_dotenv

def main():
    load_dotenv()

    exchange_id = os.getenv("EXCHANGE", "bybit")
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    testnet = os.getenv("TESTNET", "true").lower() == "true"
    symbol = os.getenv("SYMBOL", "BTCUSDT")

    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({
        "apiKey": api_key,
        "secret": api_secret,
    })

    if hasattr(exchange, "set_sandbox_mode"):
        exchange.set_sandbox_mode(testnet)

    try:
        ticker = exchange.fetch_ticker(symbol)
        print(f"✅ Connected to {exchange_id} ({'testnet' if testnet else 'prod'})")
        print(f"📌 {symbol} last price: {ticker['last']}")
    except Exception as e:
        print("❌ Connection failed:", e)

if __name__ == "__main__":
    main()
