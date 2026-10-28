"""看门狗：盯着服务和 QQ 连接，掉了自己修。

规则（每 45 秒看一次）：
- 服务（8088）没在跑  → 拉起
- 协议端（NapCat 6099 / SnowLuma 5099）没在跑 → 拉起
- 服务在跑但 QQ 连不上超过 3 分钟 → 重启协议端；再等 2 分钟还不行 → 等扫码
后端由 config.yaml 的 protocol_backend 决定，具体差异见 qqbot/proto.py。
所有动作写 logs/watchdog.log。
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)
LOCK_PORT = 9335

sys.path.insert(0, str(ROOT))
from qqbot import proto  # noqa: E402
from qqbot.account import bot_account  # noqa: E402

ACCOUNT = bot_account(ROOT)  # 不写死 QQ 号：同一份包谁装都行
BACKEND = proto.backend(ROOT)

log = logging.getLogger("watchdog")
log.setLevel(logging.INFO)
if not log.handlers:
    fh = logging.FileHandler(LOGS / "watchdog.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(fh)

_single: socket.socket | None = None


def acquire_single() -> bool:
    """靠绑定本地端口保证只有一个看门狗。

    注意：这个锁端口是给自检 / 面板探活用（连得上=看门狗在跑），
    所以必须有人 accept，否则 backlog 被占满后别人就再也连不上（误报"未运行"）。
    """
    global _single
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", LOCK_PORT))
        s.listen(16)
    except OSError:
        s.close()
        return False
    _single = s

    def _accept_forever() -> None:
        while True:
            try:
                conn, _ = s.accept()
                conn.close()
            except Exception:
                return

    threading.Thread(target=_accept_forever, name="lock-accept", daemon=True).start()
    return True


def port_open(port: int, timeout: float = 0.35) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex(("127.0.0.1", port)) == 0


def connected() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8088/status", timeout=3) as r:
            return bool(json.loads(r.read().decode()).get("connected"))
    except Exception:
        return False


def start_service() -> None:
    pyw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    exe = pyw if pyw.exists() else sys.executable
    subprocess.Popen([str(exe), "main_nb.py"], cwd=str(ROOT), close_fds=True)
    log.info("已拉起服务")


def start_napcat(quiet: bool = True) -> None:
    """名字留着（外部有引用），实际按后端分发。"""
    if proto.start(ROOT, ACCOUNT, quiet=quiet):
        log.info("已拉起协议端 %s（账号 %s）", BACKEND, ACCOUNT or "未指定")
    else:
        log.error("协议端 %s 起不来，检查目录是否完整", BACKEND)


def kill_qq() -> None:
    proto.kill_qq()
    log.info("已结束 QQ 进程，准备重启")


async def recover_login() -> None:
    try:
        import login_qr

        ok = await login_qr.drive_login()
        if ok:
            login_qr.ensure_bot()
            log.info("扫码恢复成功")
        else:
            log.warning("扫码未完成，下一轮再试")
    except Exception as exc:
        log.exception("扫码恢复异常：%r", exc)


async def main() -> None:
    if not acquire_single():
        log.info("已有看门狗在跑，退出")
        return

    log.info("看门狗启动")
    down_since: float | None = None
    restart_tried = False

    while True:
        await asyncio.sleep(45)
        try:
            svc = port_open(8088)
            if not svc:
                log.warning("服务没在跑 → 拉起")
                start_service()
                await asyncio.sleep(15)
                continue

            if not proto.is_up(ROOT):
                log.warning("协议端 %s 没在跑 → 拉起", BACKEND)
                start_napcat()
                await asyncio.sleep(20)
                continue

            if connected():
                if down_since is not None:
                    log.info("已恢复连接（掉线 %.0f 秒）", time.time() - down_since)
                down_since = None
                restart_tried = False
                continue

            # 服务在、NapCat 在，但 QQ 连不上
            if down_since is None:
                down_since = time.time()
                log.warning("QQ 连接断开，开始计时")
                continue

            down = time.time() - down_since

            if BACKEND == "snowluma":
                # SnowLuma 只能扫码登录：杀 QQ 得到的只是一个「未登录的新 QQ」，
                # 恢复不了任何东西，反而每轮都把用户刚扫上的号又打掉。
                # 所以这里只做两件事：保证协议端在、保证 QQ 窗口在，然后等人扫。
                if down > 120 and not restart_tried:
                    log.warning("掉线 %.0f 秒（SnowLuma 只能扫码，不自动重启 QQ）→ 请到 QQ 窗口扫码", down)
                    if not proto.is_up(ROOT):
                        start_napcat()
                    proto.ensure_qq(ROOT)  # 没有 QQ 就把登录窗口叫出来
                    restart_tried = True
                    await asyncio.sleep(30)
                    continue

                if down > 900:
                    log.warning("已掉线 %.0f 分钟，仍未扫码；下一轮继续等", down / 60)
                    await recover_login()
                    down_since = time.time() if not connected() else None
                    restart_tried = False
                continue

            if down > 180 and not restart_tried:
                log.warning("掉线 %.0f 秒 → 重启协议端 %s 试试", down, BACKEND)
                kill_qq()
                await asyncio.sleep(3)
                start_napcat()
                restart_tried = True
                await asyncio.sleep(60)
                continue

            if down > 420:
                log.warning("重启无效，弹二维码等扫码")
                await recover_login()
                down_since = time.time() if not connected() else None
                restart_tried = False
        except Exception as exc:
            log.exception("看门狗循环异常：%r", exc)


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass
    asyncio.run(main())
