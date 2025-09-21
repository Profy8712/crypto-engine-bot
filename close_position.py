import os
import ccxt
from dotenv import load_dotenv

def get_exchange():
    load_dotenv()
    ex = ccxt.bybit({
        "apiKey": os.getenv("API_KEY"),
        "secret": os.getenv("API_SECRET"),
        "enableRateLimit": True,
        # важно для перпетуалов
        "options": {"defaultType": "swap"},
    })
    if hasattr(ex, "set_sandbox_mode"):
        ex.set_sandbox_mode(os.getenv("TESTNET", "true").lower() == "true")
    return ex

def fetch_my_position(ex, symbol):
    # Bybit в ccxt возвращает список позиций
    positions = ex.fetch_positions([symbol])
    for p in positions:
        if p.get("symbol") == symbol:
            return p
    return None

def main():
    symbol = os.getenv("SYMBOL", "BTCUSDT")

    ex = get_exchange()
    pos = fetch_my_position(ex, symbol)

    if not pos:
        print(f"❌ No position found for {symbol}")
        return

    side = (pos.get("side") or "").lower()   # 'long' / 'short' / ''
    contracts = float(pos.get("contracts") or 0)  # количество в базовой валюте (BTC)
    entry = float(pos.get("entryPrice") or 0)
    upnl = pos.get("unrealizedPnl")

    print("📌 Current position:", {
        "side": side, "contracts": contracts, "entryPrice": entry, "uPnL": upnl
    })

    if contracts <= 0:
        print("ℹ️ Position size is zero — nothing to close.")
        return

    # Определяем противоположную сторону для закрытия
    close_side = "sell" if side == "long" else "buy" if side == "short" else None
    if close_side is None:
        print("❌ Unknown position side, abort.")
        return

    # Полное закрытие: reduceOnly market на весь объём
    params = {"reduceOnly": True}
    print(f"🧹 Closing {contracts} {symbol} by market ({close_side}, reduceOnly)")
    order = ex.create_order(symbol, "market", close_side, contracts, None, params)
    print("✅ Close order placed:", order.get("id") or order.get("orderId"))

    # Подтягиваем оставшуюся позицию
    new_pos = fetch_my_position(ex, symbol)
    if new_pos:
        print("🔎 New position:", {
            "side": new_pos.get("side"),
            "contracts": new_pos.get("contracts"),
            "entryPrice": new_pos.get("entryPrice"),
        })

if __name__ == "__main__":
    main()
