from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Sender:
    user_id: Any = 0
    nickname: str = ""
    card: str = ""
    role: str = ""  # owner / admin / member


@dataclass
class Event:
    """把 OneBot / 官方 Bot 的事件统一成这一种，插件只认它。"""

    adapter: str = ""
    type: str = "message"       # message
    sub_type: str = ""          # group / private / channel
    time: int = 0
    self_id: int = 0
    group_id: Any = None
    user_id: Any = None
    message_id: Any = None
    message: str = ""           # 纯文本
    raw_message: str = ""
    sender: Sender = field(default_factory=Sender)
    raw: dict = field(default_factory=dict)
    command_text: str = ""      # Router 填入：去掉 @机器人 后的正文

    @property
    def is_group(self) -> bool:
        return self.group_id is not None

    def __repr__(self) -> str:
        return (
            f"<Event {self.adapter}/{self.sub_type} group={self.group_id} "
            f"user={self.user_id} text={self.message[:30]!r}>"
        )
