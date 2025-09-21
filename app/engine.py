import json
from pathlib import Path
from typing import List, Tuple
from app.models import DealConfig
from app.exchanges.ccxt_client import CcxtClient
from app.utils.logger import logger

def side_to_order(side: str) -> str:
    return "buy" if side == "long" else "sell"

def exit_side(side: str) -> str:
    return "sell" if side == "long" else "buy"

class Engine:
    def __init__(self):
        self.ex = CcxtClient()
        self.tp_ids: List[str] = []
        self.grid_ids: List[str] = []

    def run(self, config_path: str):
        logger.info(f"🚀 Starting engine with config: {config_path}")

        try:
            cfg = self._load_config(config_path)
            logger.info(f"📌 Deal: {cfg.side.upper()} {cfg.symbol} @ leverage={cfg.leverage}")

            # Плечо: не валимся, если уже установлено (110043)
            try:
                self.ex.set_leverage(cfg.symbol, cfg.leverage)
            except Exception as e:
                msg = str(e)
                if "110043" in msg or "leverage not modified" in msg.lower():
                    logger.warning("ℹ️ Leverage already set, продолжаем.")
                else:
                    raise

            # 1) Вход по рынку (USDT -> qty)
            entry_side = side_to_order(cfg.side)
            last = self.ex.last_price(cfg.symbol)
            qty = round(cfg.market_order_amount / last, 6)
            order = self.ex.place_market_order(cfg.symbol, entry_side, qty)
            logger.info(f"✅ Market entry placed: {order}")

            # 2) Грид лимиток
            self._place_grid(cfg)

            # 3) Тейк-профиты (reduceOnly) от средней
            self._replace_tp(cfg)

            # 4) Мониторинг
            self._monitor_loop(cfg)

        except Exception as e:
            logger.error(f"❌ Engine failed: {e}", exc_info=True)

    # --- helpers ---
    def _load_config(self, path: str) -> DealConfig:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        cfg = DealConfig(**data)
        logger.info("⚙️ Config loaded successfully")
        return cfg

    def _place_grid(self, cfg: DealConfig):
        last = self.ex.last_price(cfg.symbol)
        n = cfg.limit_orders.orders_count
        usdt_per = cfg.limit_orders_amount / n
        r = cfg.limit_orders.range_percent / 100.0

        if cfg.side == "long":
            levels = [round(last * (1 - r * i / n), 2) for i in range(1, n + 1)]
            side = "buy"
        else:
            levels = [round(last * (1 + r * i / n), 2) for i in range(1, n + 1)]
            side = "sell"

        self.grid_ids.clear()
        for price in levels:
            qty = round(usdt_per / price, 6)
            o = self.ex.place_limit_order(cfg.symbol, side, qty, price, reduce_only=False, post_only=True)
            self.grid_ids.append(o["id"])
        logger.info(f"🧱 Placed grid orders: {len(self.grid_ids)}")

    def _position_avg_and_size(self, cfg: DealConfig) -> Tuple[float, float]:
        for p in self.ex.fetch_positions(cfg.symbol):
            if p.get("side") in ("long", "short"):
                avg = float(p.get("entryPrice") or 0.0)
                size = float(p.get("contracts") or p.get("size") or 0.0)
                return avg, size
        return 0.0, 0.0

    def _replace_tp(self, cfg: DealConfig):
        avg, size = self._position_avg_and_size(cfg)
        if avg <= 0 or size <= 0:
            logger.info("⏭ Нет активной позиции — TP не выставляем")
            return

        if self.tp_ids:
            self.ex.cancel_orders(cfg.symbol, self.tp_ids)
            self.tp_ids.clear()

        out_side = exit_side(cfg.side)
        new_ids: List[str] = []
        for tp in cfg.tp_orders:
            price = round(avg * (1 + tp.price_percent / 100.0), 2) if cfg.side == "long" \
                    else round(avg * (1 - tp.price_percent / 100.0), 2)
            qty = round(size * (tp.quantity_percent / 100.0), 6)
            if qty <= 0:
                continue
            o = self.ex.place_limit_order(cfg.symbol, out_side, qty, price, reduce_only=True, post_only=True)
            new_ids.append(o["id"])
        self.tp_ids = new_ids
        logger.info(f"🎯 Replaced TP orders: {len(self.tp_ids)}")

    def _monitor_loop(self, cfg: DealConfig):
        import time
        deadline = time.time() + cfg.limit_orders.engine_deal_duration_minutes * 60
        while True:
            try:
                open_ids = {o["id"] for o in self.ex.fetch_open_orders(cfg.symbol)}
                if any(oid not in open_ids for oid in self.grid_ids):
                    self._replace_tp(cfg)

                # TODO: реализовать stop_loss_percent, trailing_sl_offset_percent, move_sl_to_breakeven

                if time.time() > deadline:
                    still_open = [oid for oid in self.grid_ids if oid in open_ids]
                    if still_open:
                        self.ex.cancel_orders(cfg.symbol, still_open)
                    logger.info("⏹ Истёк таймер сделки — выходим из мониторинга")
                    break
            except Exception as e:
                logger.error(f"monitor error: {e}", exc_info=True)
            time.sleep(3)
