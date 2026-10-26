"""极简 CDP 客户端：直接驱动本机 Chrome/Edge，不需要 playwright。

Chrome 需带参数启动：
  chrome.exe --remote-debugging-port=9222 --user-data-dir=<持久目录>
"""

from __future__ import annotations

import asyncio
import json
import logging

import aiohttp
import websockets

log = logging.getLogger("qqbot.cdp")

DEFAULT_PORT = 9222


async def list_targets(port: int = DEFAULT_PORT) -> list[dict]:
    async with aiohttp.ClientSession() as s:
        async with s.get(f"http://127.0.0.1:{port}/json", timeout=10) as r:
            return await r.json(content_type=None)


async def pick_page(port: int = DEFAULT_PORT, match: str = "") -> dict | None:
    for t in await list_targets(port):
        if t.get("type") != "page":
            continue
        url = t.get("url") or ""
        if not match or match in url:
            return t
    return None


class Session:
    def __init__(self, ws_url: str) -> None:
        self.ws_url = ws_url
        self._id = 0
        self._ws = None

    async def __aenter__(self) -> "Session":
        self._ws = await websockets.connect(self.ws_url, max_size=20 * 1024 * 1024)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._ws:
            await self._ws.close()

    async def send(self, method: str, params: dict | None = None, timeout: float = 30) -> dict:
        self._id += 1
        mid = self._id
        await self._ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
            msg = json.loads(raw)
            if msg.get("id") == mid:
                if "error" in msg:
                    log.debug("CDP 错误 %s：%s", method, msg["error"])
                return msg.get("result") or {}

    async def js(self, expression: str, timeout: float = 30) -> any:
        res = await self.send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
            timeout=timeout,
        )
        return (res.get("result") or {}).get("value")

    async def cookies(self) -> list[dict]:
        res = await self.send("Network.getAllCookies", {"urls": ["https://www.douyin.com"]})
        return res.get("cookies") or []

    async def screenshot(self, path: str, full: bool = False, quality: int = 80, clip: dict | None = None) -> str | None:
        """截当前标签页（可指定 clip 裁剪区域），返回文件路径。"""
        import base64
        from pathlib import Path

        params: dict = {"format": "jpeg", "quality": quality, "captureBeyondViewport": bool(full or clip)}
        if clip:
            params["clip"] = clip
        try:
            res = await self.send("Page.captureScreenshot", params, timeout=30)
        except Exception as exc:
            log.warning("截图失败：%r", exc)
            return None
        data = res.get("data")
        if not data:
            return None
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(base64.b64decode(data))
        return str(dest)


async def open_session(port: int = DEFAULT_PORT, match: str = "douyin.com", url: str | None = None) -> Session | None:
    try:
        target = await pick_page(port, match)
        if target is None and url:
            async with aiohttp.ClientSession() as s:
                await s.put(f"http://127.0.0.1:{port}/json/new?{url}", timeout=15)
            await asyncio.sleep(3)
            target = await pick_page(port, match)
    except Exception as exc:
        log.debug("连不上浏览器调试端口 %d：%r", port, exc)
        return None
    if target is None:
        return None
    return Session(target["webSocketDebuggerUrl"])


async def douyin_logged_in(port: int = DEFAULT_PORT) -> bool:
    try:
        sess = await open_session(port)
    except Exception:
        return False
    if sess is None:
        return False
    try:
        async with sess:
            names = {c.get("name") for c in await sess.cookies()}
    except Exception:
        return False
    return bool({"sessionid", "sessionid_ss", "sid_tt"} & names)
