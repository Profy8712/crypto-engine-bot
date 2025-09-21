import logging
import os
from pathlib import Path

# Создаём папку logs если её нет
Path("logs").mkdir(exist_ok=True)

LOG_FILE = "logs/engine.log"

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()  # дублируем в консоль
    ]
)

logger = logging.getLogger("crypto-engine")
