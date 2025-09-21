from pydantic import BaseModel
from typing import List, Literal, Optional

class DcaLevel(BaseModel):
    price_offset_pct: float
    qty: float

class DcaConfig(BaseModel):
    enabled: bool = True
    levels: List[DcaLevel] = []
    replace_on_fill: bool = True

class TpLevel(BaseModel):
    tp_pct: float
    qty_pct: float

class TpConfig(BaseModel):
    levels: List[TpLevel]
    from_average_price: bool = True
    replace_on_reavg: bool = True

class Entry(BaseModel):
    type: Literal["market", "limit"] = "market"
    limit_price: Optional[float] = None

class Risk(BaseModel):
    max_active_orders: int = 10
    max_position_qty: float = 1.0

class DealConfig(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    base_order_qty: float
    leverage: int = 1
    margin_mode: Literal["isolated", "cross"] = "isolated"
    entry: Entry
    dca: DcaConfig
    take_profits: TpConfig
    risk: Risk
