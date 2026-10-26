from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

log = logging.getLogger("qqbot.router")

HandlerFn = Callable[[Any, Any], Awaitable[Any]]

# 群聊里常见 "＠机器人 ping"，匹配前先剥掉
_AT_PREFIX = re.compile(r"^(?:[@＠]\S+\s+)+")


@dataclass
class Handler:
    fn: HandlerFn
    priority: int = 100
    command: Optional[str] = None
    regex: Optional[re.Pattern] = None
    rule: Optional[Callable[[Any], bool]] = None
    plugin: str = ""

    def match(self, event: Any, text: str) -> bool:
        if self.command is not None:
            c = self.command
            low = text.lower()
            if not (low == c.lower() or low.startswith(c.lower() + " ") or low.startswith(c.lower() + "\u3000")):
                return False
        if self.regex is not None and not self.regex.search(text):
            return False
        if self.rule is not None and not self.rule(event):
            return False
        return True


class Router:
    def __init__(self) -> None:
        self.handlers: list[Handler] = []
        self.commands: dict[str, str] = {}  # 指令 -> 说明，help 插件用

    def on_message(
        self,
        *,
        command: Optional[str] = None,
        regex: Optional[str] = None,
        rule: Optional[Callable[[Any], bool]] = None,
        priority: int = 100,
        desc: str = "",
        plugin: str = "",
    ):
        """注册消息处理器。返回 True 表示已消化，不再传给后面的处理器。"""

        def deco(fn: HandlerFn) -> HandlerFn:
            self.handlers.append(
                Handler(
                    fn=fn,
                    priority=priority,
                    command=command,
                    regex=re.compile(regex) if isinstance(regex, str) else regex,
                    rule=rule,
                    plugin=plugin or getattr(fn, "__module__", ""),
                )
            )
            self.handlers.sort(key=lambda h: h.priority)
            if command:
                doc = (fn.__doc__ or "").strip().splitlines()
                self.commands[command] = desc or (doc[0] if doc else "")
            return fn

        return deco

    async def dispatch(self, bot: Any, event: Any) -> None:
        if event.type != "message":
            return
        text = _AT_PREFIX.sub("", event.message or "").strip()
        event.command_text = text
        for h in list(self.handlers):
            if not h.match(event, text):
                continue
            try:
                if await h.fn(bot, event) is True:
                    return
            except Exception:  # 单个插件炸掉不影响其他插件
                log.exception("插件处理异常: %s", h.plugin)
