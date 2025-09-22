from fastapi import FastAPI
from app.exchanges.ccxt_client import CcxtClient

app = FastAPI(title="Crypto Engine Monitor", version="1.0.0")

# Инициализация клиента биржи
ex = CcxtClient()


@app.get("/status")
def get_status(symbol: str = "BTC/USDT:USDT"):
    """
    Returns current position and open orders for a symbol.
    """
    try:
        pos = ex.client.fetch_positions([symbol])
    except Exception as e:
        pos = {"error": str(e)}

    try:
        orders = ex.client.fetch_open_orders(symbol)
    except Exception as e:
        orders = {"error": str(e)}

    return {"symbol": symbol, "positions": pos, "orders": orders}


@app.get("/ticker")
def get_ticker(symbol: str = "BTC/USDT:USDT"):
    """
    Returns last price for a symbol.
    """
    try:
        ticker = ex.client.fetch_ticker(symbol)
        return {"symbol": symbol, "last": ticker.get("last")}
    except Exception as e:
        return {"error": str(e)}


@app.get("/ping")
def ping():
    return {"status": "ok"}
