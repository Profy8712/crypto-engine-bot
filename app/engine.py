import json
from pathlib import Path
from app.models import DealConfig
from app.exchanges.ccxt_client import CcxtClient
from app.utils.logger import logger   # подключаем логгер


class Engine:
    def __init__(self):
        self.ex = CcxtClient()

    def run(self, config_path: str):
        logger.info(f"🚀 Starting engine with config: {config_path}")

        try:
            cfg = self._load_config(config_path)
            logger.info(f"📌 Opening {cfg.side.upper()} {cfg.symbol}, qty={cfg.base_order_qty}")

            if cfg.entry.type == "market":
                order = self.ex.place_market_order(cfg.symbol, cfg.side, cfg.base_order_qty)
                logger.info(f"✅ Market order placed: {order}")
            else:
                assert cfg.entry.limit_price, "Limit price required for limit entry"
                order = self.ex.place_limit_order(
                    cfg.symbol, cfg.side, cfg.base_order_qty, cfg.entry.limit_price
                )
                logger.info(f"✅ Limit order placed: {order}")

        except Exception as e:
            logger.error(f"❌ Engine failed: {e}", exc_info=True)

    def _load_config(self, path: str) -> DealConfig:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            cfg = DealConfig(**data)
            logger.info("⚙️ Config loaded successfully")
            return cfg
        except Exception as e:
            logger.error(f"❌ Failed to load config from {path}: {e}", exc_info=True)
            raise
