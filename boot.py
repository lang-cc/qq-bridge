"""一键启动：机器人服务 + 协议端（NapCat / SnowLuma）；掉登录时走各自的登录流程。

命令行 / 开机自启用它；桌面图标不再走这里（图标直接开网页配置台）。
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


def start_proto() -> None:
    """拉起协议端：NapCat 还是 SnowLuma 由 qqbot.proto 决定。"""
    from qqbot import proto
    from qqbot.account import bot_account

    name = proto.backend(ROOT)
    if proto.is_up(ROOT, name):
        log.info("%s 已在运行", name)
        return
    account = bot_account(ROOT)
    if proto.start(ROOT, account):
        log.info("%s 启动中…（账号 %s）", name, account or "未指定")
    else:
        log.error("%s 启动失败，检查目录是否完整", name)


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
    start_proto()

    for i in range(20):
        time.sleep(3)
        if connected():
            log.info("已连接（第 %d 秒）", (i + 1) * 3)
            ensure_watchdog()
            return 0

    from qqbot import proto

    log.warning("60 秒内没连上，判定掉登录 → %s", "等扫码" if proto.backend(ROOT) == "snowluma" else "弹二维码")
    try:
        import login_qr

        if not login_qr.start_napcat():
            log.error("%s 起不来", proto.backend(ROOT))
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
