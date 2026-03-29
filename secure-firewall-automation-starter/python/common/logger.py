from __future__ import annotations

import logging
from pathlib import Path
from .config import ROOT


def get_logger(name: str) -> logging.Logger:
    logs_dir = ROOT / "outputs" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logfile = logs_dir / "automation.log"

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    file_handler = logging.FileHandler(logfile)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger
