from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(level: str = "INFO") -> None:
    """控制台 + 文件双写。静默启动（pythonw）时没有控制台，文件日志是唯一线索。"""
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)-24s | %(message)s")
    lvl = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(lvl)
    for h in list(root.handlers):
        root.removeHandler(h)

    # 控制台（pythonw 下 sys.stdout 为 None，跳过）
    if sys.stdout is not None:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        root.addHandler(sh)

    # 文件
    try:
        log_dir = Path(os.getenv("QQBRIDGE_LOG_DIR", "logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(log_dir / "qq-bridge.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except Exception:
        pass
