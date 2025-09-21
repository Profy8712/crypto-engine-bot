import os
import ccxt
from typing import List, Any
from ccxt.base.errors import BadRequest
from .base import Exchange


_EX_MAP = {"bybit": "bybit", "gate": "gateio", "gateio": "gateio"}


class CcxtClient(Exchange):
    """
    CCXT-обёртка с нормализацией символа под линейный USDT perpetual на Bybit.
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
                    "defaultType": "swap",     # деривативы
                    "defaultSettle": "USDT",   # линейные USDT контракты
                },
            }
        )

        if hasattr(self.client, "set_sandbox_mode"):
            self.client.set_sandbox_mode(testnet)

        self.client.load_markets()

    # ----------------- helpers -----------------
    def _normalize_symbol(self, symbol: str) -> str:
        """
        Если пришёл 'BTC/USDT', пытаемся сопоставить 'BTC/USDT:USDT'
        для линейного свопа. Если уже валидный swap — вернём как есть.
        """
        if symbol in self.client.markets:
            m = self.client.market(symbol)
            if m.get("type") in ("swap", "future"):
                return symbol

        candidate = symbol if ":" in symbol else f"{symbol}/USDT:USDT" if "/" not in symbol else f"{symbol}:USDT"
        if candidate in self.client.markets:
            return candidate

        alt = symbol if ":" in symbol else (symbol.replace("USDT", "/USDT:USDT") if "USDT" in symbol and "/" not in symbol else f"{symbol}:USDT")
        if alt in self.client.markets:
            return alt

        # если ни один не найден — оставим как есть (упадём позже с понятной ошибкой)
        return symbol

    def _ensure_linear_swap(self, symbol: str):
        if symbol not in self.client.markets:
            raise ValueError(
                f"Символ {symbol} не найден в markets CCXT. "
                f"Проверь орфографию и формат (например, 'BTC/USDT:USDT')."
            )
        m = self.client.market(symbol)
        if m.get("type") != "swap" or not m.get("linear"):
            raise ValueError(
                f"Символ {symbol} не является линейным USDT perpetual. "
                f"Для Bybit используй 'BTC/USDT:USDT' и options.defaultType='swap', defaultSettle='USDT'."
            )

    def _set_modes_if_supported(self, symbol: str):
        """
        Для Bybit часто нужно заранее включить isolated и one-way (не hedge).
        Игнорируем ошибки, если режим уже установлен.
        """
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

    # ----------------- interface -----------------
    def set_leverage(self, symbol: str, leverage: int) -> Any:
        symbol = self._normalize_symbol(symbol)
        self._ensure_linear_swap(symbol)
        self._set_modes_if_supported(symbol)
        try:
            return self.client.set_leverage(leverage, symbol, {"category": "linear"})
        except BadRequest as e:
            msg = str(e)
            # мягкая обработка "leverage not modified"
            if "110043" in msg or "leverage not modified" in msg.lower():
                return {"info": {"retCode": 110043, "retMsg": "leverage not modified"}}
            raise

    def last_price(self, symbol: str) -> float:
        symbol = self._normalize_symbol(symbol)
        return float(self.client.fetch_ticker(symbol)["last"])

    def place_market_order(self, symbol: str, side: str, qty: float, reduce_only: bool = False) -> Any:
        symbol = self._normalize_symbol(symbol)
        self._ensure_linear_swap(symbol)
        params = {"reduceOnly": reduce_only} if reduce_only else {}
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
