# test_order.py
import os
import math
import ccxt
from dotenv import load_dotenv
from ccxt.base.errors import ExchangeError


def get_exchange() -> ccxt.Exchange:
    """Create CCXT exchange instance configured for Bybit USDT-perp testnet."""
    load_dotenv()
    exchange_id = os.getenv("EXCHANGE", "bybit")
    ex = getattr(ccxt, exchange_id)({
        "apiKey": os.getenv("API_KEY"),
        "secret": os.getenv("API_SECRET"),
        "enableRateLimit": True,
        "options": {
            "defaultType": "swap",      # derivatives
            "defaultSettle": "USDT",    # linear USDT contracts
        }
    })
    if hasattr(ex, "set_sandbox_mode"):
        ex.set_sandbox_mode(os.getenv("TESTNET", "true").lower() == "true")
    ex.load_markets()
    return ex


def normalize_swap_symbol(ex: ccxt.Exchange, symbol: str) -> str:
    """
    Ensure the symbol is a linear USDT perpetual like 'BTC/USDT:USDT'.
    Try to map common inputs (BTCUSDT, BTC/USDT) to swap format.
    """
    # already valid?
    if symbol in ex.markets and ex.market(symbol).get("type") in ("swap", "future"):
        return symbol

    candidates = []
    if ":" not in symbol and "/" not in symbol and symbol.endswith("USDT"):
        # BTCUSDT -> BTC/USDT:USDT
        candidates.append(f"{symbol.replace('USDT', '')}/USDT:USDT")
    if ":" not in symbol and "/" in symbol:
        # BTC/USDT -> BTC/USDT:USDT
        candidates.append(f"{symbol}:USDT")
    if ":" not in symbol and "/" not in symbol:
        # BTC -> BTC/USDT:USDT
        candidates.append(f"{symbol}/USDT:USDT")

    for c in candidates:
        if c in ex.markets and ex.market(c).get("type") in ("swap", "future"):
            return c

    raise ValueError("SYMBOL must be a linear USDT swap (e.g. BTC/USDT:USDT). "
                     f"Got '{symbol}'")


def round_amount(ex: ccxt.Exchange, symbol: str, amount: float) -> float:
    """
    Round order amount to the market precision or step.
    CCXT may provide precision as integer (number of decimals) OR as step (float).
    """
    m = ex.market(symbol)

    # 1) Try precision.amount (can be int decimals OR float step)
    prec = (m.get("precision") or {}).get("amount")
    if prec is not None:
        if isinstance(prec, int):
            # number of decimals
            return float(f"{amount:.{prec}f}")
        if isinstance(prec, float):
            # step
            step = prec
            return math.floor(amount / step) * step

    # 2) Fallback to limits.amount.step or min as step
    step = (m.get("limits", {}).get("amount", {}).get("step")
            or m.get("limits", {}).get("amount", {}).get("min")
            or 0.000001)
    return max(math.floor(amount / step) * step, 0.0)


def main():
    ex = get_exchange()
    raw_symbol = os.getenv("SYMBOL", "BTC/USDT:USDT")
    symbol = normalize_swap_symbol(ex, raw_symbol)

    side = os.getenv("SIDE", "buy").lower()  # buy/sell
    qty_env = float(os.getenv("TEST_QTY", "0.001"))
    is_testnet = os.getenv("TESTNET", "true").lower() == "true"

    # 1) Fetch last price
    last = ex.fetch_ticker(symbol)["last"]
    print(f"✅ Connected to {ex.id} ({'testnet' if is_testnet else 'prod'})")
    print(f"📌 {symbol} last: {last}")

    # 2) Round quantity per market rules
    qty = round_amount(ex, symbol, qty_env)

    # 3) Compute a passive limit price (PostOnly): below market for buy, above for sell
    price = round(last * (0.95 if side == "buy" else 1.05), 2)

    print(f"📝 Placing LIMIT {side.upper()} {qty} @ {price} (PostOnly)")
    order = ex.create_order(symbol, "limit", side, qty, price, {"timeInForce": "PostOnly"})
    oid = order.get("id") or (order.get("info") or {}).get("orderId")
    print("✅ Limit order placed:", oid)

    # 4) Verify it appears in open orders
    open_orders = ex.fetch_open_orders(symbol)
    found = any((o.get("id") == oid) or ((o.get("info") or {}).get("orderId") == oid) for o in open_orders)
    print(f"🔎 Open orders: {len(open_orders)} | found just placed: {'YES' if found else 'NO'}")

    # 5) Cancel the order
    ex.cancel_order(oid, symbol)
    print("🗑️  Canceled limit order:", oid)

    # 6) (Optional) quick market in/out
    if os.getenv("TEST_MARKET", "false").lower() == "true":
        print("⚡ TEST_MARKET=true → quick market open & close")
        m_open = ex.create_order(symbol, "market", side, qty)
        mid = m_open.get("id") or (m_open.get("info") or {}).get("orderId")
        print("   Market open:", mid)

        # fetch current position and close reduceOnly
        positions = ex.fetch_positions([symbol])
        pos = next((p for p in positions if p.get("symbol") == symbol and float(p.get("contracts") or p.get("size") or 0) > 0), None)
        if pos:
            size = float(pos.get("contracts") or pos.get("size") or 0)
            close_side = "sell" if (pos.get("side") or "").lower() == "long" else "buy"
            size = round_amount(ex, symbol, size)
            m_close = ex.create_order(symbol, "market", close_side, size, None, {"reduceOnly": True})
            cid = m_close.get("id") or (m_close.get("info") or {}).get("orderId")
            print("   Market close (reduceOnly):", cid)
        else:
            print("   ⚠️ No open position found after market open (exchange latency?).")

    print("🎉 Test finished.")


if __name__ == "__main__":
    try:
        main()
    except ExchangeError as e:
        print("❌ Exchange error:", e)
    except Exception as e:
        print("❌ Error:", e)
