"""重启机器人服务（由网页配置台的「重启服务」按钮拉起）。

为什么要单独一个脚本：重启要把当前进程杀掉，自己杀自己就没人去拉新进程了。
所以按钮只负责把本脚本以「脱离父进程」的方式启动，脚本等 1.5 秒再动手。

只杀监听 8088 / 8199 的那个 python 进程，**不动 QQ / NapCat**（杀了就得重新扫码）。

Windows：taskkill 8088/8199 的进程 → 等 1 秒 → pythonw main_nb.py
Linux  ：systemctl restart qqbridge
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PORTS = ("8088", "8199")


def _pids_on_ports() -> set[int]:
    """找监听 8088 / 8199 的进程号（只认 LISTENING）。"""
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=15,
            creationflags=CREATE_NO_WINDOW,
        ).stdout
    except Exception:
        return set()
    pids: set[int] = set()
    for line in out.splitlines():
        if "LISTENING" not in line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local = parts[1]
        if any(local.endswith(":" + p) for p in PORTS):
            try:
                pids.add(int(parts[-1]))
            except ValueError:
                pass
    pids.discard(os.getpid())
    return pids


def main() -> int:
    time.sleep(1.5)  # 等按钮那次 HTTP 请求先返回

    if os.name == "nt":
        for pid in _pids_on_ports():
            subprocess.run(["taskkill", "/f", "/pid", str(pid)],
                           creationflags=CREATE_NO_WINDOW, check=False)
        time.sleep(1.2)
        pyw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
        exe = pyw if pyw.exists() else Path(sys.executable)
        subprocess.Popen([str(exe), "main_nb.py"], cwd=str(ROOT), close_fds=True)
    else:
        subprocess.run(["systemctl", "restart", "qqbridge"], check=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
