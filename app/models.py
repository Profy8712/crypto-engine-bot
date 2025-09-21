from pydantic import BaseModel, field_validator
from typing import List, Literal


class TPItem(BaseModel):
    price_percent: float        # % от средней цены
    quantity_percent: float     # % от текущего объёма позиции


class LimitOrders(BaseModel):
    range_percent: float
    orders_count: int
    engine_deal_duration_minutes: int


class DealConfig(BaseModel):
    account: Literal["Bybit/Testnet", "Gate/Testnet"] = "Bybit/Testnet"
    symbol: str                  # для Bybit swap: "BTC/USDT:USDT"
    side: Literal["long", "short"]
    market_order_amount: float   # USDT сумма для входа по рынку
    stop_loss_percent: float
    trailing_sl_offset_percent: float
    limit_orders_amount: float   # USDT бюджет на грид усреднения
    leverage: int
    move_sl_to_breakeven: bool
    tp_orders: List[TPItem]
    limit_orders: LimitOrders

    @field_validator("tp_orders")
    @classmethod
    def _tp_sum_100(cls, items: List[TPItem]):
        s = round(sum(i.quantity_percent for i in items), 5)
        if s != 100.0:
            raise ValueError(f"Сумма quantity_percent по TP должна быть 100%, сейчас {s}")
        return items
