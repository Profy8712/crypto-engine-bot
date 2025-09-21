import os
import ccxt
from dotenv import load_dotenv

def main():
    load_dotenv()
    exchange_id = os.getenv("EXCHANGE", "bybit")
    symbol = os.getenv("SYMBOL", "BTCUSDT")
    side = "buy"
    qty = float(os.getenv("TEST_QTY", "0.001"))
    testnet = os.getenv("TESTNET", "true").lower() == "true"

    exchange_class = getattr(ccxt, exchange_id)
    ex = exchange_class({
        "apiKey": os.getenv("API_KEY"),
        "secret": os.getenv("API_SECRET"),
    })
    if hasattr(ex, "set_sandbox_mode"):
        ex.set_sandbox_mode(testnet)

    # 1) создаём лимитный ордер чуть ниже рынка
    last = ex.fetch_ticker(symbol)["last"]
    price = round(last * 0.95, 2)

    print(f"📌 Last: {last}, placing LIMIT {side} {qty} @ {price}")
    order = ex.create_order(symbol, "limit", side, qty, price)
    order_id = order.get("id") or order.get("orderId")
    print("✅ Placed order:", order_id)

    # 2) проверяем открытые ордера
    open_orders = ex.fetch_open_orders(symbol)
    print(f"🔎 Open orders count: {len(open_orders)}")

    # 3) отменяем
    ex.cancel_order(order_id, symbol)
    print("🗑️  Canceled order:", order_id)

if __name__ == "__main__":
    main()
