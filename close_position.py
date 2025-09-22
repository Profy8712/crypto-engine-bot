import os
import re
import ccxt
from dotenv import load_dotenv


def norm(sym: str) -> str:
    # BTC/USDT:USDT -> BTCUSDT
    return re.sub(r'[^A-Z0-9]', '', sym.replace(':USDT', '').upper())


def get_exchange():
    load_dotenv()
    ex = ccxt.bybit({
        "apiKey": os.getenv("API_KEY"),
        "secret": os.getenv("API_SECRET"),
        "enableRateLimit": True,
        "options": {"defaultType": "swap"},   # USDT perpetuals
    })
    if hasattr(ex, "set_sandbox_mode"):
        ex.set_sandbox_mode(os.getenv("TESTNET", "true").lower() == "true")
    return ex


def round_amount(exchange, symbol, amount: float) -> float:
    """
    Rounds amount according to market precision.
    Example: if precision=0.001 -> round to 3 decimals
    """
    market = exchange.market(symbol)
    precision = market.get("precision", {}).get("amount", None)

    if precision is None:
        return amount

    if isinstance(precision, float):
        # Example: 0.001 -> 3 decimals
        decimals = abs(int(round(-1 * (len(str(precision).split('.')[-1])))))
    else:
        decimals = int(precision)

    return float(round(amount, decimals))


def find_position(ex, target_symbol):
    try:
        positions = ex.fetch_positions()
    except Exception as e:
        print("Failed to fetch positions:", e)
        return None

    target_norm = norm(target_symbol)
    match = None
    print("📋 All positions:")
    for p in positions:
        sym = p.get("symbol") or ""
        side = (p.get("side") or "").lower()
        contracts = float(p.get("contracts") or 0)
        entry = p.get("entryPrice")
        print(f" - {sym} | side={side} | contracts={contracts} | entry={entry}")
        if norm(sym) == target_norm and abs(contracts) > 0:
            match = p
    return match


def main():
    env_symbol = os.getenv("SYMBOL", "BTC/USDT:USDT")
    ex = get_exchange()

    pos = find_position(ex, env_symbol)
    if not pos:
        print(f"❌ No open position found for {env_symbol}")
        return

    side = (pos.get("side") or "").lower()
    contracts = float(pos.get("contracts") or 0)
    entry = float(pos.get("entryPrice") or 0)

    print("📌 Position to close:", {
        "symbol": pos.get("symbol"),
        "side": side,
        "contracts": contracts,
        "entryPrice": entry,
    })

    if contracts <= 0:
        print("ℹ️ Position size is zero — nothing to close.")
        return

    qty = round_amount(ex, env_symbol, contracts)
    close_side = "sell" if side == "long" else "buy"
    params = {"reduceOnly": True}

    print(f"🧹 Closing {qty} {env_symbol} by MARKET ({close_side}, reduceOnly)")
    order = ex.create_order(env_symbol, "market", close_side, qty, None, params)
    print("✅ Close order placed:", order.get("id") or order.get("orderId"))

    pos_after = find_position(ex, env_symbol)
    if pos_after and float(pos_after.get("contracts") or 0) > 0:
        print("⚠️ Position still open:", pos_after)
    else:
        print("🎉 Position fully closed.")


if __name__ == "__main__":
    main()
