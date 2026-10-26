"""端到端自测 2：HTTP 发送接口 → 适配器 → OneBot API 调用。

运行： .venv\\Scripts\\python.exe tests\\test_send_e2e.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiohttp  # noqa: E402
import websockets  # noqa: E402

from qqbot.adapters.onebot11 import OneBot11Adapter  # noqa: E402
from qqbot.bot import Bot  # noqa: E402
from qqbot.http_api import HttpApi  # noqa: E402
from qqbot.utils_log import setup_logging  # noqa: E402

OB_PORT = 18081
OB_PATH = "/onebot/v11/ws"
API_PORT = 18088
TOKEN = "tk"


async def fake_onebot(received: list[dict], done: asyncio.Event) -> None:
    url = f"ws://127.0.0.1:{OB_PORT}{OB_PATH}"
    async with websockets.connect(url) as ws:
        done.set()
        for _ in range(3):
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            action = json.loads(raw)
            received.append(action)
            await ws.send(json.dumps({"status": "ok", "retcode": 0, "data": {"message_id": 1}, "echo": action["echo"]}))


async def main() -> int:
    setup_logging("WARNING")
    adapter = OneBot11Adapter(
        {"mode": "reverse_ws", "reverse": {"host": "127.0.0.1", "port": OB_PORT, "path": OB_PATH}}
    )
    bot = Bot(adapter)
    await bot.load_plugins()
    await adapter.start(bot)
    api = HttpApi(bot, {"host": "127.0.0.1", "port": API_PORT, "token": TOKEN})
    await api.start()
    await asyncio.sleep(0.2)

    received: list[dict] = []
    connected = asyncio.Event()
    task = asyncio.create_task(fake_onebot(received, connected))
    await asyncio.wait_for(connected.wait(), timeout=5)
    await asyncio.sleep(0.2)

    headers = {"X-Token": TOKEN}
    base = f"http://127.0.0.1:{API_PORT}"
    try:
        async with aiohttp.ClientSession() as s:
            # 1. 文字
            async with s.post(f"{base}/send/text", json={"group_id": 111, "text": "你好"}, headers=headers) as r:
                assert r.status == 200, await r.text()
            # 2. 图片（用 http URL，避免依赖本地文件）
            async with s.post(
                f"{base}/send/image", json={"group_id": 111, "src": "https://example.com/a.png"}, headers=headers
            ) as r:
                assert r.status == 200, await r.text()
            # 3. 链接卡片
            async with s.post(
                f"{base}/send/link", json={"group_id": 111, "url": "https://example.com", "title": "示例"}, headers=headers
            ) as r:
                assert r.status == 200, await r.text()
            # 4. 鉴权失败
            async with s.post(f"{base}/send/text", json={"group_id": 111, "text": "x"}) as r:
                assert r.status == 401, "token 鉴权没生效"

        await asyncio.wait_for(task, timeout=10)
    finally:
        await api.stop()
        await adapter.stop()

    assert len(received) == 3, f"期望 3 次 API 调用，实际 {len(received)}"
    kinds = []
    for action in received:
        assert action["action"] == "send_group_msg", action
        assert action["params"]["group_id"] == 111, action
        segs = action["params"]["message"]
        kinds.append(segs[0]["type"])
    assert kinds == ["text", "image", "json"], kinds
    print("\n[OK] 发送链路通过：文字 / 图片 / 链接卡片 都正确转成 OneBot 消息段，token 鉴权生效")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
