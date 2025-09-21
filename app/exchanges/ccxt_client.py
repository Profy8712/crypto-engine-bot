import os
import ccxt
from .base import Exchange

_EX_MAP = {"bybit": "bybit", "gate": "gateio", "gateio": "gateio"}

class CcxtClient(Exchange):
    def __init__(self):
        ex_name = os.getenv("EXCHANGE", "bybit").lower()
        ccxt_id = _EX_MAP.get(ex_name)
        if not ccxt_id:
            raise ValueError(f"Unknown exchange: {ex_name}")

        self.client = getattr(ccxt, ccxt_id)()
        if hasattr(self.client, "set_sandbox_mode"):
            testnet = os.getenv("TESTNET", "true").lower() == "true"
            self.client.set_sandbox_mode(testnet)

    def last_price(self, symbol: str) -> float:
        ticker = self.client.fetch_ticker(symbol)
        return float(ticker["last"])

    def place_market_order(self, symbol: str, side: str, qty: float):
        return self.client.create_order(symbol, "market", side, qty)

    def place_limit_order(self, symbol: str, side: str, qty: float, price: float):
        return self.client.create_order(symbol, "limit", side, qty, price)

    def cancel_order(self, order_id: str, symbol: str):
        return self.client.cancel_order(order_id, symbol)

    def get_open_orders(self, symbol: str):
        return self.client.fetch_open_orders(symbol)
