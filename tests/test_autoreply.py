"""自测：模拟一条私聊消息，走完整路由 → AI → 分批发送，看回复像不像人。

运行： .venv\\Scripts\\python.exe tests\\test_autoreply.py "你是谁啊 怎么突然加我"
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qqbot.bot import Bot  # noqa: E402
from qqbot.config import load_config  # noqa: E402
from qqbot.models import Event, Sender  # noqa: E402
from qqbot.utils_log import setup_logging  # noqa: E402


class StubAdapter:
    name = "stub"

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_private_msg(self, user_id, message):
        self.sent.append(str(message))
        return {"message_id": len(self.sent)}

    async def send_group_msg(self, group_id, message):
        self.sent.append(str(message))
        return {"message_id": len(self.sent)}

    async def reply(self, event, message):
        return await self.send_private_msg(event.user_id, message)

    async def call_api(self, action, params):
        return {}


async def main() -> int:
    text = sys.argv[1] if len(sys.argv) > 1 else "你是谁啊 怎么突然加我"
    setup_logging("INFO")
    cfg = load_config("config.yaml")
    adapter = StubAdapter()
    bot = Bot(adapter)
    bot.config = cfg
    bot.self_id = 1126449714
    await bot.load_plugins()

    event = Event(
        adapter="stub",
        type="message",
        sub_type="private",
        time=int(time.time()),
        user_id=123456,
        message=text,
        raw_message=text,
        sender=Sender(user_id=123456, nickname="测试"),
    )
    t0 = time.monotonic()
    await bot.router.dispatch(bot, event)
    cost = time.monotonic() - t0

    print("\n输入:", text)
    if not adapter.sent:
        print("回复: （没有回复，检查 llm.enabled / api_key）")
        return 1
    for i, seg in enumerate(adapter.sent, 1):
        print(f"回复{i}: {seg}")
    print(f"耗时: {cost:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
