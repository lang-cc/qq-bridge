from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from qqbot.bot import Bot
from qqbot.config import load_config


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="QQ 接入服务（OneBot v11 / 官方机器人）")
    p.add_argument("-c", "--config", default="config.yaml", help="配置文件路径")
    p.add_argument("--adapter", help="覆盖 adapter：onebot11 | official")
    p.add_argument("--mode", help="覆盖 onebot11.mode：reverse_ws | forward_ws | http")
    p.add_argument("--no-api", action="store_true", help="不启动本地发送接口")
    return p.parse_args()


def setup_logging(level: str) -> None:
    """控制台 + logs/qq-bridge.log 双写（静默启动时只有文件可看）。"""
    from qqbot.utils_log import setup_logging as _setup

    _setup(level)


async def amain(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    cfg.override(adapter=args.adapter)
    if args.mode:
        cfg.override(**{"onebot11.mode": args.mode})
    setup_logging(cfg.log_level)
    log = logging.getLogger("qqbot")

    from qqbot.adapters import get_adapter

    adapter = get_adapter(cfg.adapter, cfg.section(cfg.adapter))
    bot = Bot(adapter)
    bot.config = cfg
    plugins = await bot.load_plugins()
    log.info("适配器: %s | 插件: %s", adapter.name, ", ".join(plugins) or "无")

    api = None
    api_cfg = cfg.section("http_api")
    await adapter.start(bot)
    if api_cfg.get("enabled") and not args.no_api:
        from qqbot.http_api import HttpApi

        api = HttpApi(bot, api_cfg)
        await api.start()

    log.info("服务已启动，Ctrl+C 退出")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    try:
        await stop.wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        log.info("正在关闭…")
        if api is not None:
            await api.stop()
        await adapter.stop()
    return 0


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(amain(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
