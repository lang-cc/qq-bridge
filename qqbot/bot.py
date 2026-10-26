from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Any

from .router import Router


class Bot:
    """插件面向的唯一入口：收发消息 + 注册处理器，不关心底下是 OneBot 还是官方 Bot。"""

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter
        self.router = Router()
        self.log = logging.getLogger("qqbot")
        self.self_id: int = 0
        self.config: Any = None

    @property
    def name(self) -> str:
        return self.adapter.name

    # ---------- 注册 ----------
    def on_message(self, **kwargs: Any):
        return self.router.on_message(**kwargs)

    # ---------- 发消息 ----------
    async def call_api(self, action: str, **params: Any) -> dict:
        return await self.adapter.call_api(action, params)

    async def send_group_msg(self, group_id: Any, message: str) -> dict:
        return await self.adapter.send_group_msg(group_id, message)

    async def send_private_msg(self, user_id: Any, message: str) -> dict:
        return await self.adapter.send_private_msg(user_id, message)

    async def reply(self, event: Any, message: str) -> dict:
        return await self.adapter.reply(event, message)

    # ---------- 插件 ----------
    async def load_plugins(self, package: str = "qqbot.plugins") -> list[str]:
        pkg = importlib.import_module(package)
        loaded: list[str] = []
        for info in pkgutil.iter_modules(pkg.__path__):
            if info.name.startswith("_"):
                continue
            module = importlib.import_module(f"{package}.{info.name}")
            setup = getattr(module, "setup", None)
            if callable(setup):
                setup(self)
            loaded.append(info.name)
            self.log.info("插件已加载: %s", info.name)
        return loaded
