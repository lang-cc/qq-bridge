from __future__ import annotations

import time


def setup(bot) -> None:
    @bot.on_message(command="ping", priority=10, desc="测试机器人在不在")
    async def ping(bot, event):
        t0 = time.monotonic()
        await bot.reply(event, "pong 🏓")
        bot.log.debug("ping 处理耗时 %.1f ms", (time.monotonic() - t0) * 1000)
        return True
