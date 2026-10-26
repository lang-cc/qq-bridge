from __future__ import annotations

import abc
import logging
import time
from typing import Any, Optional

from ..models import Event


class Adapter(abc.ABC):
    """适配器基类：把某个平台的收发能力包成统一接口。"""

    name = "base"

    def __init__(self, cfg: Optional[dict] = None) -> None:
        self.cfg = cfg or {}
        self.bot: Any = None
        self.log = logging.getLogger(f"qqbot.adapter.{self.name}")

    async def start(self, bot: Any) -> None:
        self.bot = bot

    async def stop(self) -> None:  # noqa: D401
        pass

    # ---------- 统一收发 ----------
    async def call_api(self, action: str, params: dict) -> dict:
        raise NotImplementedError

    async def send_group_msg(self, group_id: Any, message: str) -> dict:
        return await self.call_api("send_group_msg", {"group_id": group_id, "message": message})

    async def send_private_msg(self, user_id: Any, message: str) -> dict:
        return await self.call_api("send_private_msg", {"user_id": user_id, "message": message})

    async def reply(self, event: Event, message: str) -> dict:
        if event.group_id is not None:
            return await self.send_group_msg(event.group_id, message)
        if event.user_id is not None:
            return await self.send_private_msg(event.user_id, message)
        raise ValueError("该事件没有可回复的目标")

    # ---------- 事件 -> 路由 ----------
    async def emit(self, event: Event) -> None:
        assert self.bot is not None
        await self.bot.router.dispatch(self.bot, event)

    def spawn(self, coro: Any) -> Any:
        import asyncio

        assert self.bot is not None
        task = asyncio.create_task(coro)
        task.add_done_callback(self._log_task_error)
        return task

    def _log_task_error(self, task: Any) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            self.log.error("后台任务异常: %r", exc, exc_info=exc)


def now() -> int:
    return int(time.time())
