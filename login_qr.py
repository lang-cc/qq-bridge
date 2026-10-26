"""扫码登录小工具：一键弹出 NapCat 二维码，扫完自动接上并拉起机器人。

用法：
    python login_qr.py          # 有窗口
    pythonw login_qr.py         # 无控制台

做的事：
1. NapCat 没跑就拉起来
2. 用 Edge/Chrome 的应用窗口打开登录页，自动切到「扫码登录」
3. 二维码 90 秒没扫会自动点「刷新二维码」（最多 3 次）
4. 登录成功后自动关窗口、拉起 qq-bridge 服务
"""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEBUI_PORT = 6099
ACTION_PORT = 3000
API_PORT = 8088
DEBUG_PORT = 9333
ACCOUNT = "1126449714"


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) == 0


def say(msg: str) -> None:
    print(f"[登录] {msg}", flush=True)


def webui_token() -> str:
    p = ROOT / "napcat" / "config" / "webui.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("token", "")
    except Exception:
        return ""


def find_browser() -> str | None:
    for p in (
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ):
        if Path(p).exists():
            return p
    return None


def start_napcat() -> bool:
    if port_open(WEBUI_PORT):
        say("NapCat 已经在跑")
        return True
    say("NapCat 没启动，正在拉起…")
    bat = ROOT / "napcat" / "launcher-user-silent.bat"
    if not bat.exists():
        say(f"找不到 {bat}")
        return False
    subprocess.Popen(["cmd", "/c", str(bat), "-q", ACCOUNT], cwd=str(ROOT / "napcat"),
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for _ in range(60):
        if port_open(WEBUI_PORT):
            say("NapCat 已启动")
            return True
        time.sleep(1)
    say("NapCat 启动超时")
    return False


async def drive_login() -> bool:
    """开应用窗口 → 切扫码登录 → 轮询直到登录成功。"""
    import aiohttp
    import websockets

    token = webui_token()
    url = f"http://127.0.0.1:{WEBUI_PORT}/webui/?token={token}"
    exe = find_browser()
    if not exe:
        say("找不到 Edge/Chrome")
        return False

    proc = subprocess.Popen([
        exe,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={ROOT / 'data' / 'browser-login'}",
        "--no-first-run", "--no-default-browser-check",
        "--window-size=560,820", "--window-position=200,80",
        f"--app={url}",
    ])
    say("已打开登录窗口（扫码窗口别关）")

    ws_url = None
    for _ in range(30):
        await asyncio.sleep(1)
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"http://127.0.0.1:{DEBUG_PORT}/json", timeout=5) as r:
                    for t in await r.json(content_type=None):
                        if t.get("type") == "page" and "6099" in (t.get("url") or ""):
                            ws_url = t.get("webSocketDebuggerUrl")
                            break
        except Exception:
            continue
        if ws_url:
            break
    if not ws_url:
        say("连不上登录页")
        proc.terminate()
        return False

    async with websockets.connect(ws_url, max_size=8 * 1024 * 1024) as ws:
        counter = {"id": 0}

        async def js(expr: str):
            counter["id"] += 1
            mid = counter["id"]
            await ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate",
                                      "params": {"expression": expr, "returnByValue": True}}))
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                if msg.get("id") == mid:
                    return (msg.get("result") or {}).get("result", {}).get("value")

        await asyncio.sleep(3)
        # 切到「扫码登录」
        for _ in range(10):
            ok = await js("""
            (() => {
              const el = [...document.querySelectorAll('button,[role=tab],div')]
                .find(e => (e.innerText||'').trim() === '扫码登录');
              if (el) { el.click(); return true; }
              return false;
            })()
            """)
            if ok:
                say("已切到扫码登录，请用手机 QQ 扫码")
                break
            await asyncio.sleep(1)

        # 轮询登录状态：NapCat 的 OneBot 服务起来 = 登录成功
        deadline = time.time() + 90
        refreshed = 0
        while time.time() < deadline:
            await asyncio.sleep(3)
            if port_open(ACTION_PORT):
                say("登录成功 ✅")
                await asyncio.sleep(2)
                proc.terminate()
                return True
            if time.time() > deadline - 60 and refreshed < 3:
                done = await js("""
                (() => {
                  const el = [...document.querySelectorAll('button,div,span')]
                    .find(e => (e.innerText||'').trim() === '刷新二维码');
                  if (el) { el.click(); return true; }
                  return false;
                })()
                """)
                if done:
                    refreshed += 1
                    say(f"二维码已刷新（第 {refreshed} 次）")
                    deadline = time.time() + 90
    proc.terminate()
    say("没等到登录，窗口已关，重新运行本工具即可")
    return False


def ensure_bot() -> None:
    if port_open(API_PORT):
        say("机器人服务已在跑")
        return
    say("拉起 qq-bridge 服务…")
    pyw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    if pyw.exists():
        subprocess.Popen([str(pyw), "main.py"], cwd=str(ROOT), close_fds=True)
        for _ in range(30):
            if port_open(API_PORT):
                say("服务已启动")
                return
            time.sleep(1)
    say("服务启动失败，手动运行 start_silent.vbs 看看")


async def main() -> int:
    if not start_napcat():
        return 1
    ok = await drive_login()
    if ok:
        ensure_bot()
        say("全部就绪，可以直接在 QQ 里聊了")
        return 0
    return 2


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass
    raise SystemExit(asyncio.run(main()))
