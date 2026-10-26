from __future__ import annotations

import time

START_AT = time.time()


def setup(bot) -> None:
    @bot.on_message(command="help", priority=5, desc="查看指令列表")
    async def help_cmd(bot, event):
        lines = [f"当前接入：{bot.adapter.name}"]
        for cmd, desc in sorted(bot.router.commands.items()):
            lines.append(f"· {cmd}" + (f" — {desc}" if desc else ""))
        await bot.reply(event, "\n".join(lines))
        return True

    @bot.on_message(command="菜单", priority=5)
    async def menu(bot, event):
        return await help_cmd(bot, event)

    @bot.on_message(command="状态", priority=5, desc="运行状态")
    async def status(bot, event):
        up = int(time.time() - START_AT)
        h, rem = divmod(up, 3600)
        m, s = divmod(rem, 60)
        text = (
            f"适配器：{bot.adapter.name}\n"
            f"协议端：{type(bot.adapter).__name__}\n"
            f"账号：{bot.self_id or '未同步'}\n"
            f"插件：{len(bot.router.handlers)} 个处理器\n"
            f"已运行：{h}h{m}m{s}s"
        )
        await bot.reply(event, text)
        return True
