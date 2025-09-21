import os
from dotenv import load_dotenv
from app.exchanges.ccxt_client import CcxtClient

def main():
    load_dotenv()
    symbol = os.getenv("SYMBOL", "BTCUSDT")
    ex = CcxtClient()
    price = ex.last_price(symbol)
    print(f"✅ Engine boot OK. {symbol} last price = {price}")

if __name__ == "__main__":
    main()
