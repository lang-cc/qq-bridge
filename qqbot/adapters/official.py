from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Optional

import websockets

from ..models import Event, Sender
from .base import Adapter

log = logging.getLogger("qqbot.adapter.official")


class OfficialAdapter(Adapter):
    """QQ 官方机器人（q.qq.com）：Token + WS 网关，合规、适合云端长跑。

    事件：C2C_MESSAGE_CREATE（私聊）/ GROUP_AT_MESSAGE_CREATE（群@）/ AT_MESSAGE_CREATE（频道）
    """

    name = "official"
    API = "https://api.sgroup.qq.com"
    SANDBOX_API = "https://sandbox.api.sgroup.qq.com"
    TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"

    def __init__(self, cfg: dict | None = None) -> None:
        super().__init__(cfg)
        c = self.cfg
        self.app_id = str(c.get("app_id") or "")
        self.app_secret = str(c.get("app_secret") or c.get("client_secret") or "")
        self.intents = int(c.get("intents") or (1 << 25))
        self.sandbox = bool(c.get("sandbox"))
        self.access_token = ""
        self.token_expire_at = 0.0
        self._session: Any = None
        self._ws: Any = None
        self._seq: Optional[int] = None
        self._stopping = False
        self._tasks: list[asyncio.Task] = []
        self._msg_seq: dict[str, int] = {}

    @property
    def base(self) -> str:
        return self.SANDBOX_API if self.sandbox else self.API

    # ------------------------------------------------------------ 生命周期
    async def start(self, bot: Any) -> None:
        await super().start(bot)
        if not self.app_id or not self.app_secret:
            raise ValueError("official 适配器需要 app_id 和 app_secret（QQ 开放平台 → 开发设置）")
        import aiohttp

        self._session = aiohttp.ClientSession()
        await self._refresh_token()
        self._tasks.append(self.spawn(self._ws_loop()))
        self.log.info("官方机器人适配器启动，intents=%s sandbox=%s", self.intents, self.sandbox)

    async def stop(self) -> None:
        self._stopping = True
        for task in self._tasks:
            task.cancel()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        if self._session is not None and not self._session.closed:
            await self._session.close()

    # ------------------------------------------------------------ Token
    async def _refresh_token(self) -> None:
        async with self._session.post(
            self.TOKEN_URL, json={"appId": self.app_id, "clientSecret": self.app_secret}, timeout=20
        ) as r:
            data = await r.json(content_type=None)
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"获取 access_token 失败: {data}")
        self.access_token = str(token)
        self.token_expire_at = time.time() + int(data.get("expires_in") or 7200) - 60
        self.log.info("access_token 已获取，有效期 %ss", data.get("expires_in"))

    async def _ensure_token(self) -> None:
        if time.time() >= self.token_expire_at:
            await self._refresh_token()

    # ------------------------------------------------------------ WS
    async def _ws_loop(self) -> None:
        backoff = 2
        while not self._stopping:
            try:
                await self._ensure_token()
                async with self._session.get(f"{self.base}/gateway", timeout=20) as r:
                    gw = (await r.json(content_type=None)).get("url")
                if not gw:
                    raise RuntimeError("获取 WS 网关失败")
                async with websockets.connect(gw, max_size=None) as ws:
                    self._ws = ws
                    backoff = 2
                    self.log.info("已连接官方 WS 网关")
                    await self._listen(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._stopping:
                    break
                self.log.warning("官方 WS 异常: %r，%ss 后重连", exc, backoff)
            finally:
                self._ws = None
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

    async def _listen(self, ws: Any) -> None:
        hb: Optional[asyncio.Task] = None
        try:
            async for raw in ws:
                payload = json.loads(raw)
                op = payload.get("op")
                if payload.get("s") is not None:
                    self._seq = payload.get("s")
                if op == 10:  # Hello -> 鉴权 + 心跳
                    interval = float(payload["d"]["heartbeat_interval"]) / 1000
                    await self._identify(ws)
                    hb = self.spawn(self._heartbeat(ws, interval))
                elif op == 0:  # DISPATCH
                    await self._on_dispatch(payload)
                elif op in (7, 9):  # 要求重连 / 会话失效
                    self.log.warning("收到 op=%s，准备重连", op)
                    break
        finally:
            if hb is not None:
                hb.cancel()

    async def _identify(self, ws: Any) -> None:
        await ws.send(
            json.dumps(
                {
                    "op": 2,
                    "d": {
                        "token": f"QQBot {self.access_token}",
                        "intents": self.intents,
                        "properties": {"$os": "windows", "$browser": "qqbot", "$device": "qqbot"},
                        "shard": [0, 1],
                    },
                }
            )
        )
        self.log.info("已发送鉴权（intents=%s）", self.intents)

    async def _heartbeat(self, ws: Any, interval: float) -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                await ws.send(json.dumps({"op": 1, "d": self._seq}))
            except Exception:
                return

    # ------------------------------------------------------------ 事件
    async def _on_dispatch(self, payload: dict) -> None:
        t = payload.get("t")
        d = payload.get("d") or {}
        handlers = {
            "C2C_MESSAGE_CREATE": self._on_c2c,
            "GROUP_AT_MESSAGE_CREATE": self._on_group,
            "AT_MESSAGE_CREATE": self._on_guild,
        }
        fn = handlers.get(str(t))
        if fn is not None:
            await fn(d)

    async def _on_c2c(self, d: dict) -> None:
        author = d.get("author") or {}
        openid = author.get("user_openid")
        await self.emit(
            Event(
                adapter=self.name,
                type="message",
                sub_type="private",
                time=int(d.get("timestamp") or time.time()),
                user_id=openid,
                message_id=d.get("id"),
                message=str(d.get("content") or "").strip(),
                raw_message=str(d.get("content") or ""),
                sender=Sender(user_id=openid, nickname=""),
                raw=d,
            )
        )

    async def _on_group(self, d: dict) -> None:
        author = d.get("author") or {}
        await self.emit(
            Event(
                adapter=self.name,
                type="message",
                sub_type="group",
                time=int(d.get("timestamp") or time.time()),
                group_id=d.get("group_openid"),
                user_id=author.get("member_openid"),
                message_id=d.get("id"),
                message=str(d.get("content") or "").strip(),
                raw_message=str(d.get("content") or ""),
                sender=Sender(user_id=author.get("member_openid"), nickname=""),
                raw=d,
            )
        )

    async def _on_guild(self, d: dict) -> None:
        author = d.get("author") or {}
        await self.emit(
            Event(
                adapter=self.name,
                type="message",
                sub_type="channel",
                time=int(d.get("timestamp") or time.time()),
                group_id=d.get("channel_id"),
                user_id=author.get("id"),
                message_id=d.get("id"),
                message=str(d.get("content") or "").strip(),
                raw_message=str(d.get("content") or ""),
                sender=Sender(user_id=author.get("id"), nickname=author.get("username") or ""),
                raw=d,
            )
        )

    # ------------------------------------------------------------ 发送
    def _headers(self) -> dict:
        return {"Authorization": f"QQBot {self.access_token}", "Content-Type": "application/json"}

    def _next_seq(self, msg_id: str) -> int:
        n = self._msg_seq.get(msg_id, 0) + 1
        self._msg_seq[msg_id] = n
        if len(self._msg_seq) > 2000:  # 简单防膨胀
            self._msg_seq.clear()
        return n

    async def _post(self, url: str, body: dict) -> dict:
        if self._session is None:
            import aiohttp

            self._session = aiohttp.ClientSession()
        await self._ensure_token()
        async with self._session.post(url, json=body, headers=self._headers(), timeout=20) as r:
            text = await r.text()
            if r.status >= 300:
                raise RuntimeError(f"发送失败 {r.status}: {text}")
            return json.loads(text) if text else {}

    async def reply(self, event: Event, message: str) -> dict:
        msg_id = str(event.raw.get("id") or "")
        if event.sub_type == "private":
            url = f"{self.base}/v2/users/{event.user_id}/messages"
            body = {"content": message, "msg_type": 0, "msg_id": msg_id, "msg_seq": self._next_seq(msg_id)}
        elif event.sub_type == "group":
            url = f"{self.base}/v2/groups/{event.group_id}/messages"
            body = {"content": message, "msg_type": 0, "msg_id": msg_id, "msg_seq": self._next_seq(msg_id)}
        elif event.sub_type == "channel":
            url = f"{self.base}/channels/{event.group_id}/messages"
            body = {"content": message, "msg_id": msg_id}
        else:
            raise ValueError(f"不支持回复的事件类型: {event.sub_type}")
        return await self._post(url, body)

    async def send_group_msg(self, group_id: Any, message: str) -> dict:
        # 主动消息需要额度；没有 msg_id 时官方会按主动消息处理
        return await self._post(f"{self.base}/v2/groups/{group_id}/messages", {"content": message, "msg_type": 0})

    async def send_private_msg(self, user_id: Any, message: str) -> dict:
        return await self._post(f"{self.base}/v2/users/{user_id}/messages", {"content": message, "msg_type": 0})

    async def call_api(self, action: str, params: dict) -> dict:
        raise NotImplementedError("官方机器人没有 OneBot 的 call_api 语义，请用 send_group_msg / send_private_msg / reply")
