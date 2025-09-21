import json
import time
from pathlib import Path
from typing import List, Tuple
from app.models import DealConfig
from app.exchanges.ccxt_client import CcxtClient
from app.utils.logger import logger


def side_to_order(side: str) -> str:
    # long -> buy, short -> sell
    return "buy" if side == "long" else "sell"


def exit_side(side: str) -> str:
    # TP/SL противоположной стороной
    return "sell" if side == "long" else "buy"


class Engine:
    def __init__(self):
        self.ex = CcxtClient()
        self.tp_ids: List[str] = []
        self.grid_ids: List[str] = []

        # SL / trailing / BE
        self.sl_active = False
        self.sl_price = None
        self.first_tp_done = False
        self.best_price = None  # лучшая цена в нашем направлении (для трейлинга)

    def run(self, config_path: str):
        logger.info(f"🚀 Starting engine with config: {config_path}")

        try:
            cfg = self._load_config(config_path)
            logger.info(f"📌 Deal: {cfg.side.upper()} {cfg.symbol} @ leverage={cfg.leverage}")

            # Плечо (мягкая обработка 110043)
            try:
                self.ex.set_leverage(cfg.symbol, cfg.leverage)
            except Exception as e:
                msg = str(e)
                if "110043" in msg or "leverage not modified" in msg.lower():
                    logger.warning("ℹ️ Leverage already set, продолжаем.")
                else:
                    raise

            # ===== 1) вход по рынку (USDT -> qty) =====
            entry_side = side_to_order(cfg.side)
            last = self.ex.last_price(cfg.symbol)
            qty = round(cfg.market_order_amount / last, 6)
            order = self.ex.place_market_order(cfg.symbol, entry_side, qty, reduce_only=False)
            logger.info(f"✅ Market entry placed: {order}")

            # Инициализируем SL/трейлинг от стартовой средней
            self._init_sl_trailing(cfg)

            # ===== 2) грид лимиток =====
            self._place_grid(cfg)

            # ===== 3) TP reduceOnly от средней цены =====
            self._replace_tp(cfg)

            # ===== 4) Мониторинг =====
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
        last = self._last(cfg)
        n = cfg.limit_orders.orders_count
        usdt_total = cfg.limit_orders_amount
        usdt_per = usdt_total / n
        r = cfg.limit_orders.range_percent / 100.0

        if cfg.side == "long":
            # усредняемся вниз
            levels = [round(last * (1 - r * i / n), 2) for i in range(1, n + 1)]
            side = "buy"
        else:
            # усредняемся вверх
            levels = [round(last * (1 + r * i / n), 2) for i in range(1, n + 1)]
            side = "sell"

        self.grid_ids.clear()
        for price in levels:
            qty = round(usdt_per / price, 6)
            o = self.ex.place_limit_order(
                cfg.symbol, side, qty, price, reduce_only=False, post_only=True
            )
            self.grid_ids.append(o["id"])

        logger.info(f"🧱 Placed grid orders: {len(self.grid_ids)}")

    def _position_avg_and_size(self, cfg: DealConfig) -> Tuple[float, float]:
        """
        Возвращает (avg_entry_price, size) из биржи.
        """
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

        # снимем старые TP
        if self.tp_ids:
            self.ex.cancel_orders(cfg.symbol, self.tp_ids)
            self.tp_ids.clear()

        out_side = exit_side(cfg.side)
        new_ids: List[str] = []
        for tp in cfg.tp_orders:
            price = (
                round(avg * (1 + tp.price_percent / 100.0), 2)
                if cfg.side == "long"
                else round(avg * (1 - tp.price_percent / 100.0), 2)
            )
            qty = round(size * (tp.quantity_percent / 100.0), 6)
            if qty <= 0:
                continue
            o = self.ex.place_limit_order(
                cfg.symbol, out_side, qty, price, reduce_only=True, post_only=True
            )
            new_ids.append(o["id"])

        self.tp_ids = new_ids
        logger.info(f"🎯 Replaced TP orders: {len(self.tp_ids)}")

    def _init_sl_trailing(self, cfg: DealConfig):
        """
        Инициализация уровней SL и базы для трейлинга после входа.
        """
        avg, size = self._position_avg_and_size(cfg)
        if avg <= 0 or size <= 0:
            return

        if cfg.side == "long":
            self.sl_price = round(avg * (1 - cfg.stop_loss_percent / 100.0), 2)
            self.best_price = avg  # max в пользу лонга
        else:
            self.sl_price = round(avg * (1 + cfg.stop_loss_percent / 100.0), 2)
            self.best_price = avg  # min в пользу шорта

        self.sl_active = True
        logger.info(f"🛡️  SL initialized at {self.sl_price}, trailing base={self.best_price}")

    def _maybe_move_sl_to_be(self, cfg: DealConfig, avg: float):
        """
        Перенос SL в BE после первого частичного TP.
        """
        if not cfg.move_sl_to_breakeven or self.first_tp_done:
            return

        # если хоть один TP исчез из open_orders — считаем, что сработал
        open_ids = {o["id"] for o in self.ex.fetch_open_orders(cfg.symbol)}
        if any(oid not in open_ids for oid in self.tp_ids):
            self.first_tp_done = True
            self.sl_price = round(avg, 2)
            logger.info(f"🔁 Move SL to breakeven: sl={self.sl_price}")

    def _close_market_reduce_only(self, cfg: DealConfig, size: float):
        side = exit_side(cfg.side)  # закрываем противоположной стороной
        try:
            self.ex.place_market_order(cfg.symbol, side, round(size, 6), reduce_only=True)
        except Exception as e:
            logger.error(f"Close by SL failed: {e}", exc_info=True)

    def _monitor_loop(self, cfg: DealConfig):
        """
        Простой блокирующий мониторинг:
        - проверяем исполнения лимиток грида (replace TP),
        - перенос SL в BE после первого TP,
        - трейлинг SL,
        - по таймеру сделки отменяем оставшиеся лимитки.
        """
        deadline = time.time() + cfg.limit_orders.engine_deal_duration_minutes * 60
        offset = cfg.trailing_sl_offset_percent / 100.0

        while True:
            try:
                # ---- TP replace при усреднении ----
                open_ids = {o["id"] for o in self.ex.fetch_open_orders(cfg.symbol)}
                if any(oid not in open_ids for oid in self.grid_ids):
                    self._replace_tp(cfg)

                # ---- SL/BE/Trailing ----
                avg, size = self._position_avg_and_size(cfg)
                if avg > 0 and size > 0 and self.sl_active:
                    # перенос SL в BE после первого TP
                    self._maybe_move_sl_to_be(cfg, avg)

                    last = self._last(cfg)

                    if cfg.side == "long":
                        # тянем SL за максимумом
                        if self.best_price is None or last > self.best_price:
                            self.best_price = last
                            self.sl_price = round(self.best_price * (1 - offset), 2)
                        # срабатывание SL
                        if last <= (self.sl_price or 0):
                            self._close_market_reduce_only(cfg, size)
                            logger.info(f"🛑 SL hit (long): last={last} <= sl={self.sl_price}")
                            break
                    else:
                        # short: тянем SL за минимумом
                        if self.best_price is None or last < self.best_price:
                            self.best_price = last
                            self.sl_price = round(self.best_price * (1 + offset), 2)
                        if last >= (self.sl_price or 10**18):
                            self._close_market_reduce_only(cfg, size)
                            logger.info(f"🛑 SL hit (short): last={last} >= sl={self.sl_price}")
                            break

                # ---- deadline сделки ----
                if time.time() > deadline:
                    still_open = [oid for oid in self.grid_ids if oid in open_ids]
                    if still_open:
                        self.ex.cancel_orders(cfg.symbol, still_open)
                    logger.info("⏹ Deal duration elapsed — stopping monitor loop")
                    break

            except Exception as e:
                logger.error(f"monitor error: {e}", exc_info=True)

            time.sleep(3)
