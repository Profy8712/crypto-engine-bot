from abc import ABC, abstractmethod
from typing import List, Any, Dict


class Exchange(ABC):
    # --- core trading ---
    @abstractmethod
    def set_leverage(self, symbol: str, leverage: int) -> Any:
        ...

    @abstractmethod
    def last_price(self, symbol: str) -> float:
        ...

    @abstractmethod
    def place_market_order(self, symbol: str, side: str, qty: float, reduce_only: bool = False) -> Any:
        ...

    @abstractmethod
    def place_limit_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        reduce_only: bool = False,
        post_only: bool = True,
    ) -> Any:
        ...

    @abstractmethod
    def cancel_orders(self, symbol: str, order_ids: List[str]) -> Any:
        ...

    @abstractmethod
    def fetch_open_orders(self, symbol: str) -> Any:
        ...

    @abstractmethod
    def fetch_positions(self, symbol: str) -> Any:
        ...

    # --- market helpers (for precision/limits) ---
    @abstractmethod
    def market(self, symbol: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def round_amount(self, symbol: str, amount: float) -> float:
        ...

    @abstractmethod
    def min_amount(self, symbol: str) -> float:
        ...
