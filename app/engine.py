import json
import time
from pathlib import Path
from typing import List, Tuple
from app.models import DealConfig
from app.exchanges.ccxt_client import CcxtClient
from app.utils.logger import logger


def side_to_order(side: str) -> str:
    """Convert logical side to order side."""
    return "buy" if side == "long" else "sell"


def exit_side(side: str) -> str:
    """Opposite side used to close/TP/SL."""
    return "sell" if side == "long" else "buy"


class Engine:
    def __init__(self):
        self.ex = CcxtClient()
        self.tp_ids: List[str] = []
        self.grid_ids: List[str] = []

        # SL / trailing / BE state
        self.sl_active = False
        self.sl_price = None
        self.first_tp_done = False
        self.best_price = None  # best price in our favor for trailing

    def run(self, config_path: str):
        logger.info(f"🚀 Starting engine with config: {config_path}")

        try:
            cfg = self._load_config(config_path)
            logger.info(f"📌 Deal: {cfg.side.upper()} {cfg.symbol} @ leverage={cfg.leverage}")

            # Set leverage (soft-handle "already set")
            try:
                self.ex.set_leverage(cfg.symbol, cfg.leverage)
            except Exception as e:
                msg = str(e)
                if "110043" in msg or "leverage not modified" in msg.lower():
                    logger.warning("ℹ️ Leverage already set, continue.")
                else:
                    raise

            # ===== 1) Market entry (USDT -> qty) =====
            entry_side = side_to_order(cfg.side)
            last = self._last(cfg)
            raw_qty = cfg.market_order_amount / last
            qty = self.ex.round_amount_down(cfg.symbol, raw_qty)
            min_trade = self.ex.min_tradable_amount(cfg.symbol)
            if qty < min_trade:
                raise ValueError(f"Calculated market qty {qty} < min tradable {min_trade}")
            order = self.ex.place_market_order(cfg.symbol, entry_side, qty, reduce_only=False)
            logger.info(f"✅ Market entry placed: {order}")

            # Initialize SL/Trailing from initial average
            self._init_sl_trailing(cfg)

            # ===== 2) DCA grid =====
            self._place_grid(cfg)

            # ===== 3) TP reduceOnly from average =====
            self._replace_tp(cfg)

            # ===== 4) Monitoring =====
            self._monitor_loop(cfg)

        except Exception as e:
            logger.error(f"❌ Engine failed: {e}", exc_info=True)

    # ----------------- helpers -----------------
    def _load_config(self, path: str) -> DealConfig:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        cfg = DealConfig(**data)
        logger.info("⚙️ Config loaded successfully")
        return cfg

    def _last(self, cfg: DealConfig) -> float:
        return self.ex.last_price(cfg.symbol)

    def _place_grid(self, cfg: DealConfig):
        """
        Place DCA grid in the defined range. Skip orders that fall below min tradable amount.
        """
        last = self._last(cfg)
        n = cfg.limit_orders.orders_count
        usdt_total = cfg.limit_orders_amount
        usdt_per = usdt_total / max(n, 1)
        r = cfg.limit_orders.range_percent / 100.0

        if cfg.side == "long":
            # average down
            levels = [round(last * (1 - r * i / n), 2) for i in range(1, n + 1)]
            side = "buy"
        else:
            # average up for short
            levels = [round(last * (1 + r * i / n), 2) for i in range(1, n + 1)]
            side = "sell"

        self.grid_ids.clear()
        min_trade = self.ex.min_tradable_amount(cfg.symbol)
        placed = 0
        for price in levels:
            raw_qty = usdt_per / price
            qty = self.ex.round_amount_down(cfg.symbol, raw_qty)
            if qty < min_trade:
                logger.warning(f"⚠️ Grid skip: qty {qty} < min tradable {min_trade} at price {price}")
                continue
            o = self.ex.place_limit_order(cfg.symbol, side, qty, price, reduce_only=False, post_only=True)
            self.grid_ids.append(o["id"])
            placed += 1

        logger.info(f"🧱 Placed grid orders: {placed}")

    def _position_avg_and_size(self, cfg: DealConfig) -> Tuple[float, float]:
        """
        Read (avg_entry_price, size) from exchange positions.
        """
        for p in self.ex.fetch_positions(cfg.symbol):
            if p.get("side") in ("long", "short"):
                avg = float(p.get("entryPrice") or 0.0)
                size = float(p.get("contracts") or p.get("size") or 0.0)
                return avg, size
        return 0.0, 0.0

    def _replace_tp(self, cfg: DealConfig):
        """
        Cancel previous TP orders and place new ones from current average price.
        Skip TP levels whose qty would fall below min tradable; allocate remainder on the last TP.
        """
        avg, size = self._position_avg_and_size(cfg)
        if avg <= 0 or size <= 0:
            logger.info("⏭ No active position — skip TP placement")
            return

        # cancel existing TPs
        if self.tp_ids:
            self.ex.cancel_orders(cfg.symbol, self.tp_ids)
            self.tp_ids.clear()

        out_side = exit_side(cfg.side)
        min_trade = self.ex.min_tradable_amount(cfg.symbol)
        remaining = size
        new_ids: List[str] = []

        for i, tp in enumerate(cfg.tp_orders, start=1):
            # price from average
            if cfg.side == "long":
                price = round(avg * (1 + tp.price_percent / 100.0), 2)
            else:
                price = round(avg * (1 - tp.price_percent / 100.0), 2)

            target_qty = size * (tp.quantity_percent / 100.0)
            if i == len(cfg.tp_orders):
                target_qty = remaining  # put all remainder on the last TP

            qty = self.ex.round_amount_down(cfg.symbol, target_qty)

            if qty < min_trade:
                logger.warning(f"⚠️ TP level skipped: qty {qty} < min tradable {min_trade} (price {price})")
                continue
            if qty > remaining:
                qty = self.ex.round_amount_down(cfg.symbol, remaining)
                if qty < min_trade:
                    logger.warning(f"⚠️ TP adjusted skip: qty {qty} < min tradable {min_trade} after remaining adjust")
                    continue

            o = self.ex.place_limit_order(cfg.symbol, out_side, qty, price, reduce_only=True, post_only=True)
            new_ids.append(o["id"])
            remaining = max(0.0, remaining - qty)

        self.tp_ids = new_ids
        logger.info(f"🎯 Replaced TP orders: {len(self.tp_ids)} (remaining not allocated: {remaining})")

    def _init_sl_trailing(self, cfg: DealConfig):
        """
        Initialize SL and trailing base from the current average after entry.
        """
        avg, size = self._position_avg_and_size(cfg)
        if avg <= 0 or size <= 0:
            return

        if cfg.side == "long":
            self.sl_price = round(avg * (1 - cfg.stop_loss_percent / 100.0), 2)
            self.best_price = avg  # max in favor of long
        else:
            self.sl_price = round(avg * (1 + cfg.stop_loss_percent / 100.0), 2)
            self.best_price = avg  # min in favor of short

        self.sl_active = True
        logger.info(f"🛡️  SL initialized at {self.sl_price}, trailing base={self.best_price}")

    def _maybe_move_sl_to_be(self, cfg: DealConfig, avg: float):
        """
        Move SL to breakeven after the first TP fill (detected by TP ID missing in open orders).
        """
        if not cfg.move_sl_to_breakeven or self.first_tp_done:
            return

        open_ids = {o["id"] for o in self.ex.fetch_open_orders(cfg.symbol)}
        if any(oid not in open_ids for oid in self.tp_ids):
            self.first_tp_done = True
            self.sl_price = round(avg, 2)
            logger.info(f"🔁 Move SL to breakeven: sl={self.sl_price}")

    def _close_market_reduce_only(self, cfg: DealConfig, size: float):
        side = exit_side(cfg.side)
        try:
            self.ex.place_market_order(cfg.symbol, side, round(size, 6), reduce_only=True)
        except Exception as e:
            logger.error(f"Close by SL failed: {e}", exc_info=True)

    def _monitor_loop(self, cfg: DealConfig):
        """
        Blocking monitor:
        - replace TP on grid fill (re-averaging),
        - move SL to BE after first TP,
        - trailing SL by offset percent,
        - cancel remaining grid orders on deal deadline.
        """
        deadline = time.time() + cfg.limit_orders.engine_deal_duration_minutes * 60
        offset = cfg.trailing_sl_offset_percent / 100.0

        while True:
            try:
                # ---- TP replace on grid fill ----
                open_ids_now = {o["id"] for o in self.ex.fetch_open_orders(cfg.symbol)}
                if any(oid not in open_ids_now for oid in self.grid_ids):
                    self._replace_tp(cfg)

                # ---- SL / BE / Trailing ----
                avg, size = self._position_avg_and_size(cfg)
                if avg > 0 and size > 0 and self.sl_active:
                    self._maybe_move_sl_to_be(cfg, avg)
                    last = self._last(cfg)

                    if cfg.side == "long":
                        if self.best_price is None or last > self.best_price:
                            self.best_price = last
                            self.sl_price = round(self.best_price * (1 - offset), 2)
                        if self.sl_price is not None and last <= self.sl_price:
                            self._close_market_reduce_only(cfg, size)
                            logger.info(f"🛑 SL hit (long): last={last} <= sl={self.sl_price}")
                            break
                    else:
                        if self.best_price is None or last < self.best_price:
                            self.best_price = last
                            self.sl_price = round(self.best_price * (1 + offset), 2)
                        if self.sl_price is not None and last >= self.sl_price:
                            self._close_market_reduce_only(cfg, size)
                            logger.info(f"🛑 SL hit (short): last={last} >= sl={self.sl_price}")
                            break

                # ---- deal deadline ----
                if time.time() > deadline:
                    still_open = [oid for oid in self.grid_ids if oid in open_ids_now]
                    if still_open:
                        self.ex.cancel_orders(cfg.symbol, still_open)
                    logger.info("⏹ Deal duration elapsed — stopping monitor loop")
                    break

            except Exception as e:
                logger.error(f"monitor error: {e}", exc_info=True)

            time.sleep(3)
