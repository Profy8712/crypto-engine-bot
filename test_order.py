import os
import math
import ccxt
from dotenv import load_dotenv
from ccxt.base.errors import ExchangeError


def get_exchange():
    load_dotenv()
    exchange_id = os.getenv("EXCHANGE", "bybit")
    ex = getattr(ccxt, exchange_id)({
        "apiKey": os.getenv("API_KEY"),
        "secret": os.getenv("API_SECRET"),
        "enableRateLimit": True,
        "options": {
            "defaultType": "swap",     # деривативы
            "defaultSettle": "USDT",   # линейные USDT perp
        }
    })
    if hasattr(ex, "set_sandbox_mode"):
        ex.set_sandbox_mode(os.getenv("TESTNET", "true").lower() == "true")
    ex.load_markets()
    return ex


def normalize_swap_symbol(ex: ccxt.Exchange, symbol: str) -> str:
    # Уже валидный swap?
    if symbol in ex.markets and ex.market(symbol).get("type") in ("swap", "future"):
        return symbol
    # Пробуем привести к BTC/USDT:USDT
    if ":" not in symbol and "/" not in symbol and symbol.endswith("USDT"):
        cand = f"{symbol.replace('USDT','')}/USDT:USDT"
        if cand in ex.markets: return cand
    if ":" not in symbol and "/" in symbol:
        cand = f"{symbol}:USDT"
        if cand in ex.markets: return cand
    if ":" not in symbol and "/" not in symbol:
        cand = f"{symbol}/USDT:USDT"
        if cand in ex.markets: return cand
    raise ValueError("SYMBOL must be a linear USDT swap, e.g. BTC/USDT:USDT")


def round_amount(ex: ccxt.Exchange, symbol: str, amount: float) -> float:
    m = ex.market(symbol)
    prec = m.get("precision", {}).get("amount")
    if prec is not None:
        return float(f"{amount:.{prec}f}")
    step = (m.get("limits", {}).get("amount", {}).get("min") or 0.000001)
    return max(math.floor(amount / step) * step, 0.0)


def main():
    ex = get_exchange()
    raw_symbol = os.getenv("SYMBOL", "BTC/USDT:USDT")
    symbol = normalize_swap_symbol(ex, raw_symbol)

    side = os.getenv("SIDE", "buy").lower()  # buy/sell
    qty_env = float(os.getenv("TEST_QTY", "0.001"))

    # 1) Цена рынка
    last = ex.fetch_ticker(symbol)["last"]
    print(f"✅ Connected to {ex.id} ({'testnet' if os.getenv('TESTNET','true').lower()=='true' else 'prod'})")
    print(f"📌 {symbol} last: {last}")

    # 2) Округлим количество под маркет
    qty = round_amount(ex, symbol, qty_env)

    # 3) Поставим лимитку (PostOnly), чтобы не исполнилась мгновенно
    price = round(last * (0.95 if side == "buy" else 1.05), 2)
    print(f"📝 Placing LIMIT {side.upper()} {qty} @ {price} (PostOnly)")
    order = ex.create_order(symbol, "limit", side, qty, price, {"timeInForce": "PostOnly"})
    oid = order.get("id") or (order.get("info") or {}).get("orderId")
    print("✅ Limit order placed:", oid)

    # 4) Проверим, что ордер в открытых
    open_orders = ex.fetch_open_orders(symbol)
    print(f"🔎 Open orders: {len(open_orders)}")
    found = any((o.get("id") == oid) or ((o.get("info") or {}).get("orderId") == oid) for o in open_orders)
    print("   Found placed order in open orders:", "YES" if found else "NO")

    # 5) Отменим лимитку
    ex.cancel_order(oid, symbol)
    print("🗑️  Canceled limit order:", oid)

    # 6) (Опционально) быстрый маркет-вход и закрытие reduceOnly
    do_market_test = os.getenv("TEST_MARKET", "false").lower() == "true"
    if do_market_test:
        print("⚡ TEST_MARKET=true → doing quick market open & close...")
        # open
        m_open = ex.create_order(symbol, "market", side, qty)
        mid = m_open.get("id") or (m_open.get("info") or {}).get("orderId")
        print("   Market open:", mid)

        # найдём текущую позицию и закроем reduceOnly
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
