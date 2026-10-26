from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import websockets

from ..models import Event, Sender
from .base import Adapter

log = logging.getLogger("qqbot.adapter.onebot11")


# ---------------------------------------------------------------- 事件转换
def _extract_text(message: Any, raw_message: str = "") -> str:
    """OneBot 支持字符串格式和 array 格式，统一取纯文本。"""
    if isinstance(message, str):
        return message
    if isinstance(message, list):
        parts: list[str] = []
        for seg in message:
            if not isinstance(seg, dict):
                continue
            stype = seg.get("type")
            data = seg.get("data") or {}
            if stype == "text":
                parts.append(str(data.get("text", "")))
            elif stype == "at":
                parts.append(f"@{data.get('qq')}")
            elif stype == "face":
                parts.append("[表情]")
            elif stype == "image":
                parts.append("[图片]")
        return "".join(parts)
    return raw_message or ""


def to_event(data: dict, adapter: str = "onebot11") -> Optional[Event]:
    if data.get("post_type") != "message":
        return None
    sender_raw = data.get("sender") or {}
    uid = data.get("user_id")
    return Event(
        adapter=adapter,
        type="message",
        sub_type=str(data.get("message_type") or ""),
        time=int(data.get("time") or time.time()),
        self_id=int(data.get("self_id") or 0),
        group_id=data.get("group_id"),
        user_id=uid,
        message_id=data.get("message_id"),
        message=_extract_text(data.get("message"), data.get("raw_message") or ""),
        raw_message=data.get("raw_message") or "",
        sender=Sender(
            user_id=sender_raw.get("user_id") or uid,
            nickname=sender_raw.get("nickname") or "",
            card=sender_raw.get("card") or "",
            role=sender_raw.get("role") or "",
        ),
        raw=data,
    )


# ---------------------------------------------------------------- 适配器
class OneBot11Adapter(Adapter):
    """对接 NapCat / Lagrange / LLOneBot 等 OneBot v11 协议端。"""

    name = "onebot11"

    def __init__(self, cfg: dict | None = None) -> None:
        super().__init__(cfg)
        c = self.cfg
        self.mode: str = str(c.get("mode") or "reverse_ws")
        self.access_token: str = str(c.get("access_token") or "").strip()
        self.timeout: float = float(c.get("api_timeout") or 20)
        self.reverse: dict = c.get("reverse") or {}
        self.forward: dict = c.get("forward") or {}
        self.http: dict = c.get("http") or {}

        self._ws: Any = None
        self._server: Any = None
        self._session: Any = None
        self._pending: dict[str, asyncio.Future] = {}
        self._tasks: list[asyncio.Task] = []
        self._stopping = False

    # ------------------------------------------------------------ 生命周期
    async def start(self, bot: Any) -> None:
        await super().start(bot)
        if self.mode == "reverse_ws":
            await self._start_reverse()
        elif self.mode == "forward_ws":
            self._tasks.append(self.spawn(self._forward_loop()))
            self.log.info("正向 WS 后台连接中: %s", self.forward.get("url"))
        elif self.mode == "http":
            import aiohttp

            self._session = aiohttp.ClientSession()
            self.log.info("HTTP 模式：仅调用 %s 的 API（收不到事件）", self.http.get("base_url"))
        else:
            raise ValueError(f"未知 onebot11.mode: {self.mode}")

    async def stop(self) -> None:
        self._stopping = True
        for task in self._tasks:
            task.cancel()
        if self._server is not None:
            self._server.close()
            try:
                await self._server.wait_closed()
            except Exception:
                pass
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        if self._session is not None and not self._session.closed:
            await self._session.close()
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.cancel()
        self._pending.clear()

    # ------------------------------------------------------------ 反向 WS
    async def _start_reverse(self) -> None:
        host = str(self.reverse.get("host") or "0.0.0.0")
        port = int(self.reverse.get("port") or 8080)
        path = str(self.reverse.get("path") or "/onebot/v11/ws")

        async def handler(ws: Any, req_path: str) -> None:
            req_path = req_path if isinstance(req_path, str) else ""
            if not self._path_ok(req_path, path):
                await ws.close(4004, "bad path")
                return
            if self.access_token and self._token_of(req_path, ws) != self.access_token:
                self.log.warning("拒绝连接：access_token 不匹配")
                await ws.close(4003, "invalid access_token")
                return
            self._ws = ws
            self.log.info("协议端已连上反向 WS（%s）", req_path or "/")
            self.spawn(self._sync_login_info())
            try:
                async for raw in ws:
                    await self._on_raw(raw)
            except websockets.ConnectionClosed:
                pass
            finally:
                if self._ws is ws:
                    self._ws = None
                self.log.warning("协议端连接已断开")

        self._server = await websockets.serve(handler, host, port, max_size=None)
        self.log.info("反向 WS 监听中 → ws://%s:%s%s（NapCat 里填这个地址）", host, port, path)

    def _path_ok(self, req_path: str, path: str) -> bool:
        if not self.reverse.get("strict_path"):
            return True
        return (req_path.split("?")[0] or "/") == path

    def _token_of(self, req_path: str, ws: Any = None) -> str:
        """token 可能在 URL query（NapCat 常用）、Authorization 头或 X-Token 头里。"""
        try:
            qs = parse_qs(urlparse(req_path).query)
            token = (qs.get("access_token") or qs.get("token") or [""])[0]
        except Exception:
            token = ""
        if token:
            return token
        headers = getattr(ws, "request_headers", None)
        if headers is not None:
            auth = headers.get("Authorization") or ""
            if auth.lower().startswith("bearer "):
                return auth[7:].strip()
            return headers.get("X-Token") or headers.get("X-Self-Token") or ""
        return ""

    # ------------------------------------------------------------ 正向 WS
    async def _forward_loop(self) -> None:
        url = str(self.forward.get("url") or "ws://127.0.0.1:3001")
        headers = {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}
        backoff = 1
        while not self._stopping:
            try:
                async with websockets.connect(url, extra_headers=headers, max_size=None) as ws:
                    self._ws = ws
                    backoff = 1
                    self.log.info("已连接正向 WS: %s", url)
                    self.spawn(self._sync_login_info())
                    async for raw in ws:
                        await self._on_raw(raw)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._stopping:
                    break
                self.log.warning("正向 WS 断开: %r，%ss 后重连", exc, backoff)
            finally:
                self._ws = None
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

    # ------------------------------------------------------------ 收包
    async def _on_raw(self, raw: Any) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(data, dict):
            return
        if "post_type" in data:
            event = to_event(data, self.name)
            if event is not None:
                await self._sync_login_from_event(event)
                self.spawn(self.emit(event))
        elif "echo" in data:
            fut = self._pending.get(str(data["echo"]))
            if fut is not None and not fut.done():
                fut.set_result(data)

    async def _sync_login_from_event(self, event: Event) -> None:
        if event.self_id and self.bot is not None and not self.bot.self_id:
            self.bot.self_id = event.self_id

    async def _sync_login_info(self) -> None:
        try:
            info = await self.call_api("get_login_info", {})
            self.bot.self_id = int(info.get("user_id") or 0)
            self.log.info("协议端账号: %s(%s)", info.get("nickname"), info.get("user_id"))
        except Exception as exc:
            self.log.debug("get_login_info 失败: %r", exc)

    # ------------------------------------------------------------ 调 API
    async def call_api(self, action: str, params: dict) -> dict:
        if self.mode == "http":
            return await self._http_api(action, params)
        if self._ws is None:
            raise ConnectionError(f"OneBot 协议端未连接，无法调用 {action}（先确认 NapCat 已连上来）")
        echo = uuid.uuid4().hex
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[echo] = fut
        try:
            await self._ws.send(json.dumps({"action": action, "params": params, "echo": echo}, ensure_ascii=False))
            try:
                resp = await asyncio.wait_for(fut, self.timeout)
            except asyncio.TimeoutError:
                raise TimeoutError(f"OneBot API {action} 超时（{self.timeout}s）") from None
        finally:
            self._pending.pop(echo, None)
        self._check(resp, action)
        return resp.get("data") or {}

    async def _http_api(self, action: str, params: dict) -> dict:
        import aiohttp

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        base = str(self.http.get("base_url") or "http://127.0.0.1:3000").rstrip("/")
        headers = {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}
        async with self._session.post(f"{base}/{action}", json=params, headers=headers, timeout=self.timeout) as r:
            data = await r.json(content_type=None)
        self._check(data, action)
        return data.get("data") or {}

    def _check(self, resp: dict, action: str) -> None:
        retcode = resp.get("retcode")
        if resp.get("status") == "failed" or retcode not in (0, 1):
            raise RuntimeError(f"OneBot API {action} 失败: {resp}")
