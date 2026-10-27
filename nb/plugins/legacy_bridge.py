"""把老的 qqbot.plugins.* 挂到 NoneBot2 的事件管线上。

分工：
    NoneBot2      收 NapCat 的 WebSocket、解析事件、调度、日志、生命周期
    legacy_bridge 把事件翻译成旧 Event，交给旧 Router 按 priority 派发
    老插件        记得什么、怎么回话、发不发语音 —— 一个字都没改
"""

from __future__ import annotations

import importlib
import logging

from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent

from nb.compat import LegacyBot, to_legacy
from qqbot import toggles
from qqbot.config import load_config

log = logging.getLogger("nb.bridge")

# 旧包里要挂上去的插件（跟旧 bot.load_plugins 扫描到的名单一致，_ 开头的跳过）
LEGACY_PLUGINS: tuple[str, ...] = (
    "companion",      # 陪聊主引擎：记忆 / 情绪 / 主动开聊 / 语音 / 表情包
    "help",           # help / 菜单 / 状态
    "ping",
    "echo",
    "send_tools",     # 截屏 / 发图 / 发语音 / 发链接 / 发文件
    "rules_demo",     # 正则类演示
)

SHIM = LegacyBot(load_config("config.yaml"))
_booted = False


def boot() -> None:
    """在事件循环里挂载老插件（它们会 create_task 起主动搭话等后台循环）。"""
    global _booted
    if _booted:
        return
    for name in LEGACY_PLUGINS:
        try:
            module = importlib.import_module(f"qqbot.plugins.{name}")
        except Exception:
            log.exception("老插件导入失败: %s", name)
            continue
        setup = getattr(module, "setup", None)
        if callable(setup):
            try:
                setup(SHIM)
                log.info("老插件已挂载: %s", name)
            except Exception:
                log.exception("老插件挂载失败: %s", name)
    _booted = True
    toggles.bind(SHIM.router, SHIM.config)   # 插件开关（config.yaml 的 plugins.disabled）
    off = toggles.disabled()
    if off:
        log.info("已按配置关掉插件 %d 个：%s", len(off), "、".join(sorted(off)))
    log.info("事件管线就绪｜处理器 %d 个｜指令 %d 条", len(SHIM.router.handlers), len(SHIM.router.commands))


# ---------------------------------------------------------------- 事件入口
# priority=10：框架原生指令（nb_sys 里 priority 3、block=True）先有机会认领消息；
# 没人认领时，才由这里把消息交给老引擎（记忆 / 情绪 / 陪聊那一套）。
dispatcher = on_message(priority=10)


@dispatcher.handle()
async def _dispatch(bot: Bot, event: MessageEvent) -> None:
    legacy = to_legacy(event)
    legacy.nb_bot = bot
    handled = await SHIM.router.dispatch(SHIM, legacy)
    log.debug("老引擎%s处理了这条消息: %s", "" if handled else "没有", legacy.message[:40])
