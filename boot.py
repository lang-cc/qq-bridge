"""一键启动：机器人服务 + NapCat；掉登录时自动弹二维码等扫码。

桌面上那个「QQ机器人」图标走的就是这里（通过 toggle.vbs → boot.py）。
用 pythonw 跑时没有控制台，所有输出写 logs/boot.log。
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

log = logging.getLogger("boot")
log.setLevel(logging.INFO)
if not log.handlers:
    fh = logging.FileHandler(LOGS / "boot.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(fh)


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.4) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def connected() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8088/status", timeout=3) as r:
            return bool(json.loads(r.read().decode()).get("connected"))
    except Exception:
        return False


def start_service() -> None:
    if port_open(8088):
        log.info("服务已在运行")
        return
    pyw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    exe = pyw if pyw.exists() else sys.executable
    subprocess.Popen([str(exe), "main_nb.py"], cwd=str(ROOT), close_fds=True)
    log.info("服务启动中…")


def start_napcat() -> None:
    if port_open(6099):
        log.info("NapCat 已在运行")
        return
    bat = ROOT / "napcat" / "launcher-user-silent.bat"
    if bat.exists():
        subprocess.Popen(["cmd", "/c", str(bat), "-q", "1126449714"],
                         cwd=str(ROOT / "napcat"), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        log.info("NapCat 启动中…")


def ensure_watchdog() -> None:
    """确保看门狗在跑（它自己用 9335 端口做单实例锁）。"""
    if port_open(9335):
        log.info("看门狗已在运行")
        return
    pyw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    exe = pyw if pyw.exists() else sys.executable
    try:
        subprocess.Popen([str(exe), "watchdog.py"], cwd=str(ROOT), close_fds=True)
        log.info("看门狗已启动")
    except Exception as exc:
        log.warning("看门狗启动失败：%r", exc)


async def main() -> int:
    start_service()
    start_napcat()

    for i in range(20):
        time.sleep(3)
        if connected():
            log.info("已连接（第 %d 秒）", (i + 1) * 3)
            ensure_watchdog()
            return 0

    log.warning("60 秒内没连上，判定掉登录 → 弹二维码")
    try:
        import login_qr

        if not login_qr.start_napcat():
            log.error("NapCat 起不来")
            return 1
        ok = await login_qr.drive_login()
        if ok:
            login_qr.ensure_bot()
            ensure_watchdog()
            log.info("扫码登录完成，已恢复")
            return 0
        log.warning("没等到扫码")
        ensure_watchdog()
        return 2
    except Exception as exc:
        log.exception("登录流程异常：%r", exc)
        return 3


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass
    raise SystemExit(asyncio.run(main()))
