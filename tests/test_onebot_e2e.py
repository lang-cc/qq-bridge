"""端到端自测：起真实的反向 WS 服务，用假 OneBot 客户端走一遍「收消息 → 调 API 回消息」。

运行： .venv\\Scripts\\python.exe tests\\test_onebot_e2e.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets  # noqa: E402

from qqbot.adapters.onebot11 import OneBot11Adapter  # noqa: E402
from qqbot.bot import Bot  # noqa: E402
from qqbot.utils_log import setup_logging  # noqa: E402

PORT = 18080
PATH = "/onebot/v11/ws"
TOKEN = "test-token"


async def fake_onebot(received: list[dict]) -> None:
    url = f"ws://127.0.0.1:{PORT}{PATH}?access_token={TOKEN}"
    async with websockets.connect(url) as ws:
        # 1. 推一条群消息 @机器人 ping
        await ws.send(
            json.dumps(
                {
                    "post_type": "message",
                    "message_type": "group",
                    "sub_type": "normal",
                    "time": 1730000000,
                    "self_id": 10000,
                    "group_id": 88888,
                    "user_id": 123456,
                    "message_id": 42,
                    "message": [{"type": "at", "data": {"qq": "10000"}}, {"type": "text", "data": {"text": " ping"}}],
                    "raw_message": "@机器人 ping",
                    "sender": {"user_id": 123456, "nickname": "测试员", "card": "", "role": "member"},
                },
                ensure_ascii=False,
            )
        )
        # 2. 期望收到 send_group_msg
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        action = json.loads(raw)
        received.append(action)
        assert action["action"] == "send_group_msg", action
        assert action["params"]["group_id"] == 88888, action
        assert "pong" in action["params"]["message"], action
        # 3. 回执
        await ws.send(json.dumps({"status": "ok", "retcode": 0, "data": {"message_id": 99}, "echo": action["echo"]}))
        await asyncio.sleep(0.2)


async def main() -> int:
    setup_logging("INFO")
    adapter = OneBot11Adapter(
        {
            "mode": "reverse_ws",
            "access_token": TOKEN,
            "reverse": {"host": "127.0.0.1", "port": PORT, "path": PATH},
        }
    )
    bot = Bot(adapter)
    await bot.load_plugins()
    await adapter.start(bot)
    await asyncio.sleep(0.2)

    received: list[dict] = []
    try:
        await fake_onebot(received)
    finally:
        await adapter.stop()

    assert received, "没有收到机器人发出的 API 调用"
    print("\n[OK] E2E 通过：消息进 → 插件处理 → API 出，全链路正常")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
