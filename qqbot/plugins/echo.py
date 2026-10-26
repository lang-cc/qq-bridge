from __future__ import annotations


def setup(bot) -> None:
    @bot.on_message(command="echo", priority=50, desc="复读：echo 内容")
    async def echo(bot, event):
        parts = event.command_text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await bot.reply(event, "用法：echo 要复读的内容")
        else:
            await bot.reply(event, parts[1].strip())
        return True
