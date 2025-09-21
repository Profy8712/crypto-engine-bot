import os
from dotenv import load_dotenv

def main():
    load_dotenv()
    symbol = os.getenv("SYMBOL", "BTCUSDT")
    print(f"Engine boot OK. SYMBOL={symbol}")

if __name__ == "__main__":
    main()
