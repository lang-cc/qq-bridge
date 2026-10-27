"""框架原生插件：用 NoneBot 的 on_command 写的指令。

跟老插件（qqbot.plugins.*）并存：
    /nb        看框架状态（版本、连接、处理器数量、运行时长）
    /nbhelp    框架侧自带的指令
聊天正文仍然交给 legacy_bridge 里的老引擎，互不干扰。
"""

from __future__ import annotations

import time

import nonebot
from nonebot import on_command
from nonebot.rule import Rule

from qqbot import toggles


def _on() -> bool:
    """「插件」页里把「框架指令」关掉后，/nb 就不再认领消息。"""
    return toggles.is_enabled("nb.plugins.nb_sys")
from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent
from nonebot.params import CommandArg

START_AT = time.time()


def _uptime() -> str:
    up = int(time.time() - START_AT)
    h, rem = divmod(up, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m}m{s}s"


nb_cmd = on_command("nb", aliases={"框架状态", "framework"}, priority=3, block=True, rule=Rule(_on))


@nb_cmd.handle()
async def _nb_status(bot: Bot, event: MessageEvent, args: Message = CommandArg()) -> None:
    import nonebot
    from importlib.metadata import version as _pkg_version

    from nb.compat import current_bot
    from nb.plugins import legacy_bridge

    try:
        ob_version = _pkg_version("nonebot-adapter-onebot")
    except Exception:
        ob_version = "?"

    bots = nonebot.get_bots()
    active = current_bot()
    handlers = len(legacy_bridge.SHIM.router.handlers)
    commands = len(legacy_bridge.SHIM.router.commands)
    lines = [
        "NoneBot2 运行时",
        f"· 框架 nonebot2 {nonebot.__version__} / onebot 适配器 {ob_version}",
        f"· 驱动 {type(nonebot.get_driver()).__name__}",
        f"· 已连协议端 {len(bots)} 个" + (f"（当前 {active.self_id}）" if active else "（未连接）"),
        f"· 已加载插件 {len(nonebot.get_loaded_plugins())} 个",
        f"· 老引擎处理器 {handlers} 个 / 指令 {commands} 条",
        f"· 运行 {_uptime()}",
    ]
    await nb_cmd.finish("\n".join(lines))


nb_help = on_command("nbhelp", aliases={"框架帮助"}, priority=3, block=True, rule=Rule(_on))


@nb_help.handle()
async def _nb_help() -> None:
    import nonebot

    names = sorted(p.name for p in nonebot.get_loaded_plugins())
    await nb_help.finish(
        "框架侧指令：\n"
        "· /nb（或「框架状态」）看运行状态\n"
        "· /nbhelp 看这条\n"
        f"· 已加载插件：{', '.join(names) or '无'}\n"
        "聊天指令（help / 人格 / 记忆 / 查看心情 …）仍由老引擎处理。"
    )
