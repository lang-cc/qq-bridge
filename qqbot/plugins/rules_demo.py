"""演示规则类插件：不走指令，用正则 + 发送者身份。

用法：群里说 "谁是管理" / "打卡" 试试。
"""

from __future__ import annotations

import re


def setup(bot) -> None:
    @bot.on_message(regex=r"^(谁是管理|管理员是谁)", priority=60)
    async def who_is_admin(bot, event):
        sender = event.sender
        role = sender.role or "member"
        name = sender.card or sender.nickname or sender.user_id
        await bot.reply(event, f"{name} 的身份是 {role}")
        return True

    @bot.on_message(regex=r"^打卡$", priority=60)
    async def checkin(bot, event):
        await bot.reply(event, f"收到打卡：{event.sender.nickname or event.user_id}")
        return True
