import sys
import pathlib

# Ensure project root is on sys.path so "import app" works when running as a file.
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load environment variables from .env before importing the engine.
from dotenv import load_dotenv
load_dotenv()

from app.engine import Engine


def main():
    """
    Run trading engine with a JSON config path.

    Usage:
        python scripts/run_deal.py deal_config.json
    or:
        python -m scripts.run_deal deal_config.json
    """
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_deal.py <config_path.json>")
        sys.exit(1)

    cfg_path = sys.argv[1]
    Engine().run(cfg_path)


if __name__ == "__main__":
    main()
