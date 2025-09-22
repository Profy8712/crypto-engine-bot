from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, List, Literal

# Load .env early so ccxt client and other components see env vars.
from dotenv import load_dotenv
load_dotenv()

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Query,
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

# Optional: engine import (not required for API itself).
try:
    from app.engine import Engine  # noqa: F401
    _ENGINE_AVAILABLE = True
except Exception:
    _ENGINE_AVAILABLE = False


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(title="Crypto Engine Monitor", version="1.0.0")

# Enable CORS if the UI may be opened from another origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB (SQLite by default).
init_db()

# Global exchange client used by monitoring endpoints.
ex = CcxtClient()

# Serve static UI files (monitor.html, JS, CSS).
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_event(ev: TradeEvent) -> dict:
    """Convert SQLModel TradeEvent to a JSON-serializable dict."""
    data = ev.model_dump()  # SQLModel with Pydantic v2
    ts = data.get("ts")
    if isinstance(ts, datetime):
        data["ts"] = ts.isoformat()
    return jsonable_encoder(data)


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------

@app.get("/ping")
def ping():
    """Health check."""
    return {"status": "ok"}


@app.get("/status")
def status(symbol: str = Query("BTC/USDT:USDT", description="Trading symbol")):
    """Return open positions and active orders for a symbol."""
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
    """Return last traded price for a symbol."""
    try:
        t = ex.client.fetch_ticker(symbol)
        return {"symbol": symbol, "last": t.get("last")}
    except Exception as e:
        return {"error": str(e)}


@app.get("/ohlcv")
def ohlcv(
    symbol: str = Query("BTC/USDT:USDT", description="Trading symbol"),
    timeframe: str = Query("1m", description="Candle timeframe"),
    limit: int = Query(200, ge=10, le=2000, description="Number of candles"),
):
    """
    Return OHLCV candles via ccxt.
    Response items: {time (sec), open, high, low, close, volume}
    """
    try:
        data = ex.client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        out = [
            {
                "time": int(c[0] / 1000),  # ms -> sec (Lightweight Charts expects seconds)
                "open": c[1],
                "high": c[2],
                "low": c[3],
                "close": c[4],
                "volume": c[5],
            }
            for c in data
        ]
        return {"symbol": symbol, "timeframe": timeframe, "candles": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/events")
def events(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    type: Optional[Literal["entry", "grid", "tp", "sl", "sl_move_be"]] = Query(
        None, description="Filter by event type"
    ),
    limit: int = Query(200, ge=1, le=2000, description="Number of events to return"),
):
    """Return latest trade events from local SQLite DB."""
    with Session(db_engine) as session:
        stmt = select(TradeEvent).order_by(TradeEvent.ts.desc()).limit(limit)
        rows: List[TradeEvent] = session.exec(stmt).all()

        # Apply filters in memory (dataset is small).
        if symbol:
            rows = [r for r in rows if r.symbol == symbol]
        if type:
            rows = [r for r in rows if r.type == type]

        return [_serialize_event(r) for r in rows]


@app.get("/monitor")
def monitor_page():
    """Serve the monitoring HTML page with realtime chart and markers."""
    return FileResponse("app/static/monitor.html")


# ---------------------------------------------------------------------------
# WebSocket for realtime events
# ---------------------------------------------------------------------------

@app.websocket("/ws/stream")
async def stream(ws: WebSocket):
    """Stream trade events to the frontend in realtime."""
    await ws.accept()
    q = bus.subscribe("events")
    try:
        while True:
            event = await q.get()
            await ws.send_json(event)
    except WebSocketDisconnect:
        # Client disconnected — just exit the handler.
        return
