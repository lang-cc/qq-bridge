"""Linux 看门狗：服务和 QQ 掉了自己修（Docker 版）。

规则（每 45 秒一轮）：
- 8088 不在 → systemctl restart qqbridge
- 6099 不在 → docker restart napcat
- QQ 连不上超过 3 分钟 → docker restart napcat（再等 2 分钟仍不行 → 重新出二维码）

锁定端口 9335：既是单实例锁，也让 selfcheck 能判断它在跑。
"""

from __future__ import annotations

import json
import logging
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)
LOCK_PORT = 9335
CONTAINER = "napcat"
SERVICE = "qqbridge"

log = logging.getLogger("watchdog")
log.setLevel(logging.INFO)
if not log.handlers:
    fh = logging.FileHandler(LOGS / "watchdog.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(fh)

_single: socket.socket | None = None


def acquire_single() -> bool:
    global _single
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", LOCK_PORT))
        s.listen(1)
    except OSError:
        s.close()
        return False
    _single = s
    return True


def port_open(port: int, timeout: float = 0.6) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex(("127.0.0.1", port)) == 0


def connected() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8088/status", timeout=4) as r:
            return bool(json.loads(r.read().decode()).get("connected"))
    except Exception:
        return False


def sh(cmd: list[str], timeout: int = 120) -> None:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, text=True)
        if r.returncode != 0:
            log.warning("命令失败 %s：%s", " ".join(cmd), (r.stderr or "").strip()[:200])
    except Exception as exc:
        log.warning("命令异常 %s：%r", " ".join(cmd), exc)


def main() -> None:
    if not acquire_single():
        log.info("已有看门狗在跑，退出")
        return

    log.info("看门狗启动（Linux / Docker 模式）")
    down_since: float | None = None
    restarted = False

    while True:
        time.sleep(45)
        try:
            if not port_open(8088):
                log.warning("服务没在跑 → 重启 qqbridge")
                sh(["systemctl", "restart", SERVICE])
                time.sleep(20)
                continue

            if not port_open(6099):
                log.warning("NapCat 没在跑 → 重启容器")
                sh(["docker", "restart", CONTAINER])
                time.sleep(30)
                continue

            if connected():
                if down_since is not None:
                    log.info("已恢复连接（掉线 %.0f 秒）", time.time() - down_since)
                down_since = None
                restarted = False
                continue

            if down_since is None:
                down_since = time.time()
                log.warning("QQ 连接断开，开始计时")
                continue

            down = time.time() - down_since
            if down > 180 and not restarted:
                log.warning("掉线 %.0f 秒 → 重启 NapCat", down)
                sh(["docker", "restart", CONTAINER])
                restarted = True
                time.sleep(60)
                continue

            if down > 420:
                log.warning("重启无效，等人工扫码（看 http://<IP>:6099）")
                down_since = time.time()
                restarted = False
        except Exception as exc:
            log.exception("看门狗循环异常：%r", exc)


if __name__ == "__main__":
    main()
