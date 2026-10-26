"""NoneBot2 ↔ 老引擎的适配层。

框架（NoneBot2 + nonebot-adapter-onebot）负责：
    - 和 NapCat 的反向 WebSocket 连接、断线重连、心跳
    - 事件解析（MessageEvent）、分发管线、优先级 / 阻断
    - 插件生命周期、日志、热重载

老的 ``qqbot.*`` 业务模块（记忆 / 情绪 / 人格 / 语音 / 表情包 / 抖音 / 主动开聊）
一行都不用改：它们只认一个「bot 对象」，本模块把它造出来，再把收发转接给
当前连上的 NoneBot Bot。
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

import nonebot
from nonebot.adapters.onebot.v11 import Bot as OneBot11Bot
from nonebot.adapters.onebot.v11.event import MessageEvent as OneBot11MessageEvent

from qqbot.config import Config
from qqbot.models import Event, Sender
from qqbot.router import Router

log = logging.getLogger("nb.compat")

# 纯文本化时的占位符，跟旧 adapters/onebot11.py 保持一致
PLACEHOLDER = {
    "face": "[表情]",
    "image": "[图片]",
    "record": "[语音]",
    "video": "[视频]",
    "file": "[文件]",
    "mface": "[表情]",
}


# ------------------------------------------------------------------ 工具
def current_bot() -> OneBot11Bot | None:
    """当前连着的 OneBot v11 Bot（NoneBot 里可能有多个账号，取第一个）。"""
    for bot in nonebot.get_bots().values():
        if isinstance(bot, OneBot11Bot):
            return bot
    return None


def _segments(message: Iterable[Any]) -> list[dict]:
    """NoneBot Message → OneBot v11 消息段数组（原样可发回 NapCat）。"""
    out: list[dict] = []
    for seg in message or []:
        stype = getattr(seg, "type", "") or ""
        data = dict(getattr(seg, "data", {}) or {})
        if stype == "text":
            out.append({"type": "text", "data": {"text": str(data.get("text", ""))}})
        else:
            clean = {k: v for k, v in data.items() if isinstance(v, (str, int, float, bool))}
            out.append({"type": stype, "data": clean})
    return out


def _plain(message: Iterable[Any]) -> str:
    """消息段数组 → 纯文本（@ 保留成 @QQ，表情/图片转占位符），跟旧适配器一致。"""
    parts: list[str] = []
    for seg in message or []:
        stype = getattr(seg, "type", "") or ""
        data = dict(getattr(seg, "data", {}) or {})
        if stype == "text":
            parts.append(str(data.get("text", "")))
        elif stype == "at":
            parts.append(f"@{data.get('qq')}")
        elif stype in PLACEHOLDER:
            parts.append(PLACEHOLDER[stype])
    return "".join(parts)


def to_nb_message(payload: Any) -> Any:
    """旧代码的 payload（str / 段数组 / 单段）→ NoneBot Message，走框架原生 send 时用。"""
    try:
        from nonebot.adapters.onebot.v11 import Message, MessageSegment
    except Exception:  # 没装适配器时原样返回
        return payload
    if isinstance(payload, str):
        return Message(payload)
    items = payload if isinstance(payload, (list, tuple)) else [payload]
    segments = []
    for item in items:
        if isinstance(item, dict) and item.get("type"):
            segments.append(MessageSegment(str(item["type"]), dict(item.get("data") or {})))
        elif isinstance(item, str):
            segments.append(MessageSegment("text", {"text": item}))
    return Message(segments) if segments else Message(str(payload))


def to_legacy(event: OneBot11MessageEvent) -> Event:
    """NoneBot 事件 → 旧引擎认识的 Event（字段与旧适配器完全一致）。"""
    sender_raw = getattr(event, "sender", None)
    mtype = str(getattr(event, "message_type", "") or ("group" if getattr(event, "group_id", None) else "private"))
    segs = _segments(getattr(event, "message", []) or [])
    try:
        self_id = int(getattr(event, "self_id", 0) or 0)
    except Exception:
        self_id = 0

    legacy = Event(
        adapter="onebot11",
        type="message",
        sub_type=mtype,  # 旧代码就是这么取的：message_type
        time=int(getattr(event, "time", 0) or 0),
        self_id=self_id,
        group_id=getattr(event, "group_id", None),
        user_id=getattr(event, "user_id", None),
        message_id=getattr(event, "message_id", None),
        message=_plain(getattr(event, "message", []) or []),
        raw_message=str(getattr(event, "raw_message", "") or ""),
        sender=Sender(
            user_id=getattr(sender_raw, "user_id", None) or getattr(event, "user_id", None),
            nickname=str(getattr(sender_raw, "nickname", "") or ""),
            card=str(getattr(sender_raw, "card", "") or ""),
            role=str(getattr(sender_raw, "role", "") or ""),
        ),
        raw={
            "post_type": "message",
            "message_type": mtype,
            "sub_type": str(getattr(event, "sub_type", "") or ""),
            "self_id": self_id,
            "time": int(getattr(event, "time", 0) or 0),
            "group_id": getattr(event, "group_id", None),
            "user_id": getattr(event, "user_id", None),
            "message_id": getattr(event, "message_id", None),
            "message": segs,
            "raw_message": str(getattr(event, "raw_message", "") or ""),
        },
    )
    legacy.nb_bot = None  # 调用方补上，回复时优先用它
    legacy.nb_event = event
    return legacy


# ------------------------------------------------------------------ 适配对象
class ShimAdapter:
    """冒充旧 adapter：给 http_api / help 插件看的那几个属性。"""

    name = "onebot11"

    def __init__(self, bot: "LegacyBot") -> None:
        self._bot = bot

    @property
    def _ws(self) -> Any:
        """http_api 的 /status 用它判断是否在线。"""
        return current_bot()

    async def call_api(self, action: str, params: dict | None = None) -> dict:
        return await self._bot.call_api(action, **(params or {}))

    async def send_group_msg(self, group_id: Any, message: Any) -> dict:
        return await self._bot.send_group_msg(group_id, message)

    async def send_private_msg(self, user_id: Any, message: Any) -> dict:
        return await self._bot.send_private_msg(user_id, message)

    async def reply(self, event: Any, message: Any) -> dict:
        return await self._bot.reply(event, message)


class LegacyBot:
    """旧插件眼里的 bot：on_message 注册 + 收发消息 + config。"""

    name = "onebot11"

    def __init__(self, config: Config) -> None:
        self.config = config
        self.router = Router()
        self.adapter = ShimAdapter(self)
        self.log = logging.getLogger("qqbot")

    # ---------- 注册（仍然是旧的 @bot.on_message 写法） ----------
    def on_message(self, **kwargs: Any):
        return self.router.on_message(**kwargs)

    # ---------- 信息 ----------
    @property
    def self_id(self) -> int:
        bot = current_bot()
        try:
            return int(bot.self_id) if bot is not None else 0
        except Exception:
            return 0

    @property
    def connected(self) -> bool:
        return current_bot() is not None

    # ---------- 收发 ----------
    async def call_api(self, action: str, **params: Any) -> Any:
        bot = current_bot()
        if bot is None:
            raise ConnectionError(f"OneBot 协议端未连接，无法调用 {action}（先确认 NapCat 连上了 /onebot/v11/ws）")
        return await bot.call_api(action, **params)

    async def send_group_msg(self, group_id: Any, message: Any) -> dict:
        return await self.call_api("send_group_msg", group_id=group_id, message=message) or {}

    async def send_private_msg(self, user_id: Any, message: Any) -> dict:
        return await self.call_api("send_private_msg", user_id=user_id, message=message) or {}

    async def reply(self, event: Any, message: Any) -> dict:
        gid = getattr(event, "group_id", None)
        uid = getattr(event, "user_id", None)
        if gid is not None:
            return await self.send_group_msg(gid, message)
        if uid is not None:
            return await self.send_private_msg(uid, message)
        raise ValueError("该事件没有可回复的目标")

    async def reply_to_source(self, event: Any, message: Any) -> dict:
        """优先走 NoneBot 原生 send（拿得到 message_id，也支持引用回复场景）。"""
        bot = getattr(event, "nb_bot", None) or current_bot()
        nb_event = getattr(event, "nb_event", None)
        if bot is None or nb_event is None:
            return await self.reply(event, message)
        return await bot.send(nb_event, to_nb_message(message)) or {}
