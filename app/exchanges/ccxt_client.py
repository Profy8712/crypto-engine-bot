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

        api_key = os.getenv("API_KEY")
        api_secret = os.getenv("API_SECRET")
        testnet = os.getenv("TESTNET", "true").lower() == "true"

        # передаём ключи в клиент
        self.client = getattr(ccxt, ccxt_id)({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
        })

        # включаем тестнет (если поддерживается)
        if hasattr(self.client, "set_sandbox_mode"):
            self.client.set_sandbox_mode(testnet)

        # для Bybit лучше указать unified/swap тип (иначе может путаться)
        if ccxt_id == "bybit":
            self.client.options = { **self.client.options, "defaultType": "swap" }

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
