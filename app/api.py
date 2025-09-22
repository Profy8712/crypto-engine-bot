from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, List, Literal

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Query,
    BackgroundTasks,
    HTTPException,
)
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sqlmodel import Session, select

from app.event_bus import bus
from app.db import init_db, TradeEvent, engine as db_engine
from app.exchanges.ccxt_client import CcxtClient

# optional: run trading engine from API
try:
    from app.engine import Engine
    _ENGINE_AVAILABLE = True
except Exception:
    _ENGINE_AVAILABLE = False


# ---------------------------------------------------------------------------
# FastAPI app initialization
# ---------------------------------------------------------------------------

app = FastAPI(title="Crypto Engine Monitor", version="1.0.0")

# enable CORS if UI will be opened from another domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# initialize database (SQLite by default)
init_db()

# global exchange client (for monitoring only)
ex = CcxtClient()

# static UI files (monitor.html etc.)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_event(ev: TradeEvent) -> dict:
    """Convert SQLModel TradeEvent -> dict for JSON response."""
    data = ev.model_dump()  # SQLModel is compatible with Pydantic v2
    ts = data.get("ts")
    if isinstance(ts, datetime):
        data["ts"] = ts.isoformat()
    return jsonable_encoder(data)


# ---------------------------------------------------------------------------
# REST API endpoints
# ---------------------------------------------------------------------------

@app.get("/ping")
def ping():
    """Healthcheck endpoint."""
    return {"status": "ok"}


@app.get("/status")
def status(symbol: str = Query("BTC/USDT:USDT", description="Trading symbol")):
    """Return current open positions and active orders from exchange."""
    try:
        positions = ex.client.fetch_positions([symbol])
    except Exception as e:
        positions = {"error": str(e)}

    try:
        orders = ex.client.fetch_open_orders(symbol)
    except Exception as e:
        orders = {"error": str(e)}

    return {"symbol": symbol, "positions": positions, "orders": orders}


@app.get("/ticker")
def ticker(symbol: str = Query("BTC/USDT:USDT", description="Trading symbol")):
    """Return last traded price for given symbol."""
    try:
        t = ex.client.fetch_ticker(symbol)
        return {"symbol": symbol, "last": t.get("last")}
    except Exception as e:
        return {"error": str(e)}


@app.get("/events")
def events(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    type: Optional[Literal["entry", "grid", "tp", "sl", "sl_move_be"]] = Query(
        None, description="Filter by event type"
    ),
    limit: int = Query(200, ge=1, le=2000, description="Number of events to return"),
):
    """Return latest events from local DB (SQLite)."""
    with Session(db_engine) as session:
        stmt = select(TradeEvent).order_by(TradeEvent.ts.desc()).limit(limit)
        rows: List[TradeEvent] = session.exec(stmt).all()

        # apply filters in memory (lightweight because dataset is small)
        if symbol:
            rows = [r for r in rows if r.symbol == symbol]
        if type:
            rows = [r for r in rows if r.type == type]

        return [_serialize_event(r) for r in rows]


@app.get("/monitor")
def monitor_page():
    """Serve monitoring HTML page with realtime chart."""
    return FileResponse("app/static/monitor.html")


# ---------------------------------------------------------------------------
# WebSocket endpoint for realtime events
# ---------------------------------------------------------------------------

@app.websocket("/ws/stream")
async def stream(ws: WebSocket):
    """Push new events to frontend in realtime via WebSocket."""
    await ws.accept()
    q = bus.subscribe("events")
    try:
        while True:
            event = await q.get()
            await ws.send_json(event)
    except WebSocketDisconnect:
        # client disconnected
        return
