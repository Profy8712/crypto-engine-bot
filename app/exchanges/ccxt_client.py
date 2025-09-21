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
    Includes symbol normalization, leverage handling and market helpers.
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
                    "defaultType": "swap",      # derivatives
                    "defaultSettle": "USDT",    # linear USDT contracts
                },
            }
        )

        if hasattr(self.client, "set_sandbox_mode"):
            self.client.set_sandbox_mode(testnet)

        self.client.load_markets()

    # ----------------- internal helpers -----------------
    def _normalize_symbol(self, symbol: str) -> str:
        """
        Map common inputs like 'BTCUSDT' or 'BTC/USDT' to a linear swap 'BTC/USDT:USDT'.
        If already a valid swap in markets — return as is.
        """
        if symbol in self.client.markets:
            m = self.client.market(symbol)
            if m.get("type") in ("swap", "future"):
                return symbol

        # Try common candidates
        candidates = []
        if ":" not in symbol and "/" not in symbol and symbol.endswith("USDT"):
            candidates.append(f"{symbol.replace('USDT', '')}/USDT:USDT")  # BTCUSDT -> BTC/USDT:USDT
        if ":" not in symbol and "/" in symbol:
            candidates.append(f"{symbol}:USDT")                            # BTC/USDT -> BTC/USDT:USDT
        if ":" not in symbol and "/" not in symbol:
            candidates.append(f"{symbol}/USDT:USDT")                       # BTC -> BTC/USDT:USDT

        for c in candidates:
            if c in self.client.markets:
                m = self.client.market(c)
                if m.get("type") in ("swap", "future"):
                    return c

        # If still not found, return as is (will raise in _ensure_linear_swap)
        return symbol

    def _ensure_linear_swap(self, symbol: str):
        if symbol not in self.client.markets:
            # refresh once if needed
            self.client.load_markets()
        if symbol not in self.client.markets:
            raise ValueError(
                f"Symbol {symbol} not found in CCXT markets. "
                f"Use a linear swap like 'BTC/USDT:USDT'."
            )
        m = self.client.market(symbol)
        if m.get("type") != "swap" or not m.get("linear"):
            raise ValueError(
                f"Symbol {symbol} is not a linear USDT perpetual. "
                f"Use 'BTC/USDT:USDT' with options.defaultType='swap', defaultSettle='USDT'."
            )

    def _set_modes_if_supported(self, symbol: str):
        """
        For Bybit it's often required to set isolated margin and one-way position mode.
        Ignore errors if already set or unsupported.
        """
        params = {"category": "linear"}
        try:
            if hasattr(self.client, "set_margin_mode"):
                self.client.set_margin_mode("isolated", symbol, params)
        except Exception:
            pass
        try:
            if hasattr(self.client, "set_position_mode"):
                self.client.set_position_mode(False, symbol, params)  # one-way (not hedged)
        except Exception:
            pass

    # ----------------- Exchange interface -----------------
    def set_leverage(self, symbol: str, leverage: int) -> Any:
        symbol = self._normalize_symbol(symbol)
        self._ensure_linear_swap(symbol)
        self._set_modes_if_supported(symbol)
        try:
            return self.client.set_leverage(leverage, symbol, {"category": "linear"})
        except BadRequest as e:
            msg = str(e)
            # Soft-handle Bybit's "leverage not modified"
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

    # ----------------- market helpers -----------------
    def market(self, symbol: str) -> Dict[str, Any]:
        symbol = self._normalize_symbol(symbol)
        if symbol not in self.client.markets:
            self.client.load_markets()
        return self.client.market(symbol)

    def round_amount(self, symbol: str, amount: float) -> float:
        """
        Round amount to market precision/step.
        CCXT sometimes provides precision as decimals (int) or step (float).
        """
        m = self.market(symbol)
        prec = (m.get("precision") or {}).get("amount")
        if isinstance(prec, int):
            return float(f"{amount:.{prec}f}")
        if isinstance(prec, float) and prec > 0:
            step = prec
            return math.floor(amount / step) * step

        step = (m.get("limits", {}).get("amount", {}).get("step")
                or m.get("limits", {}).get("amount", {}).get("min")
                or 0.000001)
        return max(math.floor(amount / step) * step, 0.0)

    def min_amount(self, symbol: str) -> float:
        m = self.market(symbol)
        return float(m.get("limits", {}).get("amount", {}).get("min") or 0.0)
