import json
import time
from pathlib import Path
from typing import List, Tuple, Optional
from ccxt.base.errors import InvalidOrder
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

        # SL / trailing / BE
        self.sl_active = False
        self.sl_price: Optional[float] = None
        self.first_tp_done = False
        self.best_price: Optional[float] = None

    def run(self, config_path: str):
        logger.info(f"🚀 Starting engine with config: {config_path}")
        try:
            cfg = self._load_config(config_path)
            logger.info(f"📌 Deal: {cfg.side.upper()} {cfg.symbol} @ leverage={cfg.leverage}")

            # leverage
            try:
                self.ex.set_leverage(cfg.symbol, cfg.leverage)
            except Exception as e:
                msg = str(e)
                if "110043" in msg or "leverage not modified" in msg.lower():
                    logger.warning("ℹ️ Leverage already set, continue.")
                else:
                    raise

            # 1) Market entry (USDT -> qty)
            entry_side = side_to_order(cfg.side)
            last = self._last(cfg)
            raw_qty = cfg.market_order_amount / last
            step = self.ex.amount_step(cfg.symbol)
            min_trade = self.ex.min_tradable_amount(cfg.symbol)
            qty = self.ex.round_amount_down(cfg.symbol, raw_qty)

            logger.info(f"➡️ Entry calc: last={last}, raw_qty={raw_qty}, step={step}, min_tradable={min_trade}, qty_rounded={qty}")
            if qty < min_trade:
                raise ValueError(f"Calculated market qty {qty} < min tradable {min_trade}")
            order = self.ex.place_market_order(cfg.symbol, entry_side, qty, reduce_only=False)
            logger.info(f"✅ Market entry placed: {order}")

            # init SL/trailing
            self._init_sl_trailing(cfg)

            # 2) DCA grid
            self._place_grid(cfg)

            # 3) TP from avg
            self._replace_tp(cfg)

            # 4) monitor
            self._monitor_loop(cfg)

        except Exception as e:
            logger.error(f"❌ Engine failed: {e}", exc_info=True)

    # ---- helpers ----
    def _load_config(self, path: str) -> DealConfig:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        cfg = DealConfig(**data)
        logger.info("⚙️ Config loaded successfully")
        return cfg

    def _last(self, cfg: DealConfig) -> float:
        return self.ex.last_price(cfg.symbol)

    # ---------- safe order wrapper ----------
    def _safe_limit_order(self, symbol: str, side: str, qty: float, price: float, reduce_only: bool, post_only: bool):
        """
        Place a limit order, but if Bybit returns 110017 (qty truncated to zero),
        skip gracefully and return None.
        """
        try:
            return self.ex.place_limit_order(symbol, side, qty, price, reduce_only=reduce_only, post_only=post_only)
        except InvalidOrder as e:
            msg = str(e)
            if "110017" in msg or "truncated to zero" in msg.lower():
                logger.warning(f"⚠️ Skipped limit order by exchange filter (110017): side={side}, qty={qty}, price={price}")
                return None
            raise

    def _place_grid(self, cfg: DealConfig):
        last = self._last(cfg)
        n = cfg.limit_orders.orders_count
        usdt_total = cfg.limit_orders_amount
        usdt_per = usdt_total / max(n, 1)
        r = cfg.limit_orders.range_percent / 100.0

        if cfg.side == "long":
            raw_levels = [last * (1 - r * i / n) for i in range(1, n + 1)]
            side = "buy"
        else:
            raw_levels = [last * (1 + r * i / n) for i in range(1, n + 1)]
            side = "sell"

        levels = [self.ex.round_price_to_tick(cfg.symbol, p) for p in raw_levels]

        self.grid_ids.clear()
        min_trade = self.ex.min_tradable_amount(cfg.symbol)
        step = self.ex.amount_step(cfg.symbol)
        placed = 0
        for price in levels:
            raw_qty = usdt_per / price
            qty = self.ex.round_amount_down(cfg.symbol, raw_qty)
            logger.info(f"🧩 Grid level: price_raw={raw_qty*price:.8f}@{price}, qty_raw={raw_qty}, step={step}, min_tradable={min_trade}, qty_rounded={qty}")
            if qty < min_trade:
                logger.warning(f"⚠️ Grid skip: qty {qty} < min tradable {min_trade} @ {price}")
                continue
            o = self._safe_limit_order(cfg.symbol, side, qty, price, reduce_only=False, post_only=True)
            if o:
                self.grid_ids.append(o["id"])
                placed += 1

        logger.info(f"🧱 Placed grid orders: {placed}")

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
            logger.info("⏭ No active position — skip TP placement")
            return

        # cancel old
        if self.tp_ids:
            self.ex.cancel_orders(cfg.symbol, self.tp_ids)
            self.tp_ids.clear()

        out_side = exit_side(cfg.side)
        min_trade = self.ex.min_tradable_amount(cfg.symbol)
        step = self.ex.amount_step(cfg.symbol)
        remaining = size
        new_ids: List[str] = []

        for i, tp in enumerate(cfg.tp_orders, start=1):
            # price from avg (rounded to tick)
            raw_price = avg * (1 + tp.price_percent / 100.0) if cfg.side == "long" \
                        else avg * (1 - tp.price_percent / 100.0)
            price = self.ex.round_price_to_tick(cfg.symbol, raw_price)

            target_qty = size * (tp.quantity_percent / 100.0)
            if i == len(cfg.tp_orders):
                target_qty = remaining

            qty = self.ex.round_amount_down(cfg.symbol, target_qty)
            logger.info(f"🎯 TP level {i}: price_raw={raw_price}, price={price}, "
                        f"target_qty={target_qty}, step={step}, min_tradable={min_trade}, qty_rounded={qty}")

            if qty < min_trade:
                logger.warning(f"⚠️ TP skip: qty {qty} < min tradable {min_trade} @ {price}")
                continue
            if qty > remaining:
                qty = self.ex.round_amount_down(cfg.symbol, remaining)
                logger.info(f"   TP adjust to remaining: new_qty={qty}, remaining_before={remaining}")
                if qty < min_trade:
                    logger.warning(f"⚠️ TP adjusted skip: qty {qty} < min tradable {min_trade}")
                    continue

            o = self._safe_limit_order(cfg.symbol, out_side, qty, price, reduce_only=True, post_only=True)
            if o:
                new_ids.append(o["id"])
                remaining = max(0.0, remaining - qty)

        self.tp_ids = new_ids
        logger.info(f"🎯 Replaced TP orders: {len(self.tp_ids)} (remaining not allocated: {remaining})")

    def _init_sl_trailing(self, cfg: DealConfig):
        avg, size = self._position_avg_and_size(cfg)
        if avg <= 0 or size <= 0:
            return
        if cfg.side == "long":
            self.sl_price = self.ex.round_price_to_tick(cfg.symbol, avg * (1 - cfg.stop_loss_percent / 100.0))
            self.best_price = avg
        else:
            self.sl_price = self.ex.round_price_to_tick(cfg.symbol, avg * (1 + cfg.stop_loss_percent / 100.0))
            self.best_price = avg
        self.sl_active = True
        logger.info(f"🛡️  SL initialized at {self.sl_price}, trailing base={self.best_price}")

    def _maybe_move_sl_to_be(self, cfg: DealConfig, avg: float):
        if not cfg.move_sl_to_breakeven or self.first_tp_done:
            return
        open_ids = {o["id"] for o in self.ex.fetch_open_orders(cfg.symbol)}
        if any(oid not in open_ids for oid in self.tp_ids):
            self.first_tp_done = True
            self.sl_price = self.ex.round_price_to_tick(cfg.symbol, avg)
            logger.info(f"🔁 Move SL to breakeven: sl={self.sl_price}")

    def _close_market_reduce_only(self, cfg: DealConfig, size: float):
        side = exit_side(cfg.side)
        try:
            self.ex.place_market_order(cfg.symbol, side, round(size, 6), reduce_only=True)
        except Exception as e:
            logger.error(f"Close by SL failed: {e}", exc_info=True)

    def _monitor_loop(self, cfg: DealConfig):
        deadline = time.time() + cfg.limit_orders.engine_deal_duration_minutes * 60
        offset = cfg.trailing_sl_offset_percent / 100.0

        while True:
            try:
                open_ids_now = {o["id"] for o in self.ex.fetch_open_orders(cfg.symbol)}
                if any(oid not in open_ids_now for oid in self.grid_ids):
                    self._replace_tp(cfg)

                avg, size = self._position_avg_and_size(cfg)
                if avg > 0 and size > 0 and self.sl_active:
                    self._maybe_move_sl_to_be(cfg, avg)
                    last = self._last(cfg)

                    if cfg.side == "long":
                        if self.best_price is None or last > self.best_price:
                            self.best_price = last
                            self.sl_price = self.ex.round_price_to_tick(cfg.symbol, self.best_price * (1 - offset))
                        if self.sl_price is not None and last <= self.sl_price:
                            self._close_market_reduce_only(cfg, size)
                            logger.info(f"🛑 SL hit (long): last={last} <= sl={self.sl_price}")
                            break
                    else:
                        if self.best_price is None or last < self.best_price:
                            self.best_price = last
                            self.sl_price = self.ex.round_price_to_tick(cfg.symbol, self.best_price * (1 + offset))
                        if self.sl_price is not None and last >= self.sl_price:
                            self._close_market_reduce_only(cfg, size)
                            logger.info(f"🛑 SL hit (short): last={last} >= sl={self.sl_price}")
                            break

                if time.time() > deadline:
                    still_open = [oid for oid in self.grid_ids if oid in open_ids_now]
                    if still_open:
                        self.ex.cancel_orders(cfg.symbol, still_open)
                    logger.info("⏹ Deal duration elapsed — stopping monitor loop")
                    break

            except Exception as e:
                logger.error(f"monitor error: {e}", exc_info=True)

            time.sleep(3)
