import os
import math
import ccxt
from typing import List, Any, Dict
from ccxt.base.errors import BadRequest
from .base import Exchange


_EX_MAP = {"bybit": "bybit", "gate": "gateio", "gateio": "gateio"}


class CcxtClient(Exchange):
    """
    CCXT wrapper configured for Bybit/Gate USDT perpetuals.
    Robust symbol normalization + leverage + precise qty/price rounding.
    """

    def __init__(self):
        ex_name = (os.getenv("EXCHANGE") or "bybit").lower()
        ccxt_id = _EX_MAP.get(ex_name)
        if not ccxt_id:
            raise ValueError(f"Unknown exchange: {ex_name}")

        api_key = os.getenv("API_KEY") or os.getenv("BYBIT_API_KEY")
        api_secret = os.getenv("API_SECRET") or os.getenv("BYBIT_API_SECRET")
        testnet = (os.getenv("TESTNET", "true").lower() == "true")

        self.client = getattr(ccxt, ccxt_id)(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "swap",
                    "defaultSettle": "USDT",
                },
            }
        )
        if hasattr(self.client, "set_sandbox_mode"):
            self.client.set_sandbox_mode(testnet)
        self.client.load_markets()

    # ---------- internal helpers ----------
    def _normalize_symbol(self, symbol: str) -> str:
        if symbol in self.client.markets:
            m = self.client.market(symbol)
            if m.get("type") in ("swap", "future"):
                return symbol

        candidates = []
        if ":" not in symbol and "/" not in symbol and symbol.endswith("USDT"):
            candidates.append(f"{symbol.replace('USDT', '')}/USDT:USDT")
        if ":" not in symbol and "/" in symbol:
            candidates.append(f"{symbol}:USDT")
        if ":" not in symbol and "/" not in symbol:
            candidates.append(f"{symbol}/USDT:USDT")

        for c in candidates:
            if c in self.client.markets:
                m = self.client.market(c)
                if m.get("type") in ("swap", "future"):
                    return c
        return symbol

    def _ensure_linear_swap(self, symbol: str):
        if symbol not in self.client.markets:
            self.client.load_markets()
        if symbol not in self.client.markets:
            raise ValueError(f"Symbol {symbol} not found. Use 'BTC/USDT:USDT'.")
        m = self.client.market(symbol)
        if m.get("type") != "swap" or not m.get("linear"):
            raise ValueError(f"{symbol} is not linear USDT perpetual (expected 'BTC/USDT:USDT').")

    def _set_modes_if_supported(self, symbol: str):
        params = {"category": "linear"}
        try:
            if hasattr(self.client, "set_margin_mode"):
                self.client.set_margin_mode("isolated", symbol, params)
        except Exception:
            pass
        try:
            if hasattr(self.client, "set_position_mode"):
                self.client.set_position_mode(False, symbol, params)  # one-way
        except Exception:
            pass

    # ---------- Exchange interface ----------
    def set_leverage(self, symbol: str, leverage: int) -> Any:
        symbol = self._normalize_symbol(symbol)
        self._ensure_linear_swap(symbol)
        self._set_modes_if_supported(symbol)
        try:
            return self.client.set_leverage(leverage, symbol, {"category": "linear"})
        except BadRequest as e:
            msg = str(e)
            if "110043" in msg or "leverage not modified" in msg.lower():
                return {"info": {"retCode": 110043, "retMsg": "leverage not modified"}}
            raise

    def last_price(self, symbol: str) -> float:
        symbol = self._normalize_symbol(symbol)
        return float(self.client.fetch_ticker(symbol)["last"])

    def place_market_order(self, symbol: str, side: str, qty: float, reduce_only: bool = False) -> Any:
        symbol = self._normalize_symbol(symbol)
        self._ensure_linear_swap(symbol)
        params = {"reduceOnly": True} if reduce_only else {}
        return self.client.create_order(symbol, "market", side, qty, None, params)

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        reduce_only: bool = False,
        post_only: bool = True,
    ) -> Any:
        symbol = self._normalize_symbol(symbol)
        self._ensure_linear_swap(symbol)
        params = {"reduceOnly": reduce_only}
        if post_only:
            params["timeInForce"] = "PostOnly"
        # NB: caller is expected to round qty/price to step/tick already
        return self.client.create_order(symbol, "limit", side, qty, price, params)

    def cancel_orders(self, symbol: str, order_ids: List[str]) -> Any:
        symbol = self._normalize_symbol(symbol)
        out = []
        for oid in order_ids:
            try:
                out.append(self.client.cancel_order(oid, symbol))
            except Exception:
                pass
        return out

    def fetch_open_orders(self, symbol: str) -> Any:
        symbol = self._normalize_symbol(symbol)
        return self.client.fetch_open_orders(symbol)

    def fetch_positions(self, symbol: str) -> Any:
        symbol = self._normalize_symbol(symbol)
        positions = self.client.fetch_positions([symbol])
        return [p for p in positions if p.get("symbol") == symbol]

    # ---------- market helpers ----------
    def market(self, symbol: str) -> Dict[str, Any]:
        symbol = self._normalize_symbol(symbol)
        if symbol not in self.client.markets:
            self.client.load_markets()
        return self.client.market(symbol)

    def amount_step(self, symbol: str) -> float:
        m = self.market(symbol)
        prec = (m.get("precision") or {}).get("amount")
        if isinstance(prec, int):
            return 10 ** (-prec) if prec >= 0 else 1e-6
        if isinstance(prec, float) and prec > 0:
            return prec
        step = (m.get("limits", {}).get("amount", {}).get("step")
                or m.get("limits", {}).get("amount", {}).get("min")
                or 1e-6)
        return float(step)

    def min_amount(self, symbol: str) -> float:
        m = self.market(symbol)
        return float(m.get("limits", {}).get("amount", {}).get("min") or 0.0)

    def min_tradable_amount(self, symbol: str) -> float:
        return max(self.amount_step(symbol), self.min_amount(symbol))

    def round_amount_down(self, symbol: str, amount: float) -> float:
        step = self.amount_step(symbol)
        if step <= 0:
            return max(amount, 0.0)
        return math.floor(amount / step) * step

    def price_step(self, symbol: str) -> float:
        m = self.market(symbol)
        prec = (m.get("precision") or {}).get("price")
        if isinstance(prec, int):
            return 10 ** (-prec) if prec >= 0 else 1e-2
        if isinstance(prec, float) and prec > 0:
            return prec
        tick = (m.get("limits", {}).get("price", {}).get("step")
                or m.get("limits", {}).get("price", {}).get("min")
                or 0.1)
        return float(tick)

    def round_price_to_tick(self, symbol: str, price: float) -> float:
        tick = self.price_step(symbol)
        if tick <= 0:
            return price
        return math.floor(price / tick) * tick
