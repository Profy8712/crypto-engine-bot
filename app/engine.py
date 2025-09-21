import json
from pathlib import Path
from app.models import DealConfig
from app.exchanges.ccxt_client import CcxtClient

class Engine:
    def __init__(self):
        self.ex = CcxtClient()

    def run(self, config_path: str):
        cfg = self._load_config(config_path)
        print(f"📌 Opening {cfg.side} {cfg.symbol} qty={cfg.base_order_qty}")
        if cfg.entry.type == "market":
            order = self.ex.place_market_order(cfg.symbol, cfg.side, cfg.base_order_qty)
            print("✅ Market order placed:", order)
        else:
            assert cfg.entry.limit_price, "Limit price required for limit entry"
            order = self.ex.place_limit_order(cfg.symbol, cfg.side, cfg.base_order_qty, cfg.entry.limit_price)
            print("✅ Limit order placed:", order)

    def _load_config(self, path: str) -> DealConfig:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return DealConfig(**data)
