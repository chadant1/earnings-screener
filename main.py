"""Earnings Pattern Screener – entry point.

    python main.py          # normal mode (downloads real market data)
    python main.py --demo   # simulated data, no internet needed
"""
import logging
import sys


def _setup_logging():
    from screener.config import app_data_dir
    log_path = app_data_dir() / "app.log"
    # windowed (no-console) builds have no stdout/stderr; send everything to a log file
    if sys.stdout is None or sys.stderr is None:
        f = open(log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or f
        sys.stderr = sys.stderr or f
    logging.basicConfig(filename=str(log_path), level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


if __name__ == "__main__":
    _setup_logging()
    from screener.gui.main_window import run
    sys.exit(run(demo="--demo" in sys.argv))
