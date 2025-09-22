from fastapi import FastAPI, WebSocket
from app.exchanges.ccxt_client import CcxtClient
from app.db import init_db, TradeEvent, engine
from sqlmodel import Session, select
from app.event_bus import bus

app = FastAPI(title="Crypto Engine Monitor", version="1.0.0")

# Init DB
init_db()
ex = CcxtClient()


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/status")
def status(symbol: str = "BTC/USDT:USDT"):
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
def ticker(symbol: str = "BTC/USDT:USDT"):
    try:
        t = ex.client.fetch_ticker(symbol)
        return {"symbol": symbol, "last": t.get("last")}
    except Exception as e:
        return {"error": str(e)}


@app.get("/events")
def events(limit: int = 50):
    with Session(engine) as session:
        stmt = select(TradeEvent).order_by(TradeEvent.ts.desc()).limit(limit)
        rows = session.exec(stmt).all()
        return [row.dict() for row in rows]


@app.websocket("/ws/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    q = bus.subscribe("events")
    while True:
        event = await q.get()
        await ws.send_json(event)
