"""群里可用的发送类指令：截屏 / 发图 / 发语音 / 发链接 / 发文件。"""

from __future__ import annotations

from .. import message as msg
from ..screenshot import capture_desktop, capture_url


def setup(bot) -> None:
    @bot.on_message(command="截屏", priority=20, desc="截本机屏幕发到群里")
    async def shot(bot, event):
        path = capture_desktop()
        await bot.reply(event, [msg.image(path)])
        return True

    @bot.on_message(command="网页截屏", priority=20, desc="网页截屏：网页截屏 https://example.com")
    async def web_shot(bot, event):
        parts = event.command_text.split(maxsplit=1)
        if len(parts) < 2:
            await bot.reply(event, "用法：网页截屏 https://example.com")
            return True
        try:
            path = capture_url(parts[1].strip())
        except Exception as exc:
            await bot.reply(event, f"截屏失败：{exc}")
            return True
        await bot.reply(event, [msg.image(path)])
        return True

    @bot.on_message(command="发图", priority=20, desc="发图 <本地路径或图片URL>")
    async def send_pic(bot, event):
        parts = event.command_text.split(maxsplit=1)
        if len(parts) < 2:
            await bot.reply(event, "用法：发图 E:/pics/1.png 或 发图 https://xx.com/a.jpg")
            return True
        await bot.reply(event, [msg.image(parts[1].strip())])
        return True

    @bot.on_message(command="发语音", priority=20, desc="发语音 <音频路径>")
    async def send_voice(bot, event):
        parts = event.command_text.split(maxsplit=1)
        if len(parts) < 2:
            await bot.reply(event, "用法：发语音 E:/audio/1.mp3（会自动转 silk）")
            return True
        from ..voice import prepare

        await bot.reply(event, [msg.record(prepare(parts[1].strip()))])
        return True

    @bot.on_message(command="发文件", priority=20, desc="发文件 <路径>")
    async def send_file(bot, event):
        parts = event.command_text.split(maxsplit=1)
        if len(parts) < 2:
            await bot.reply(event, "用法：发文件 E:/docs/a.pdf")
            return True
        await bot.reply(event, [msg.file(parts[1].strip())])
        return True

    @bot.on_message(command="发链接", priority=20, desc="发链接 <url> [标题]")
    async def send_link(bot, event):
        parts = event.command_text.split(maxsplit=2)
        if len(parts) < 2:
            await bot.reply(event, "用法：发链接 https://example.com 标题")
            return True
        url = parts[1].strip()
        title = parts[2].strip() if len(parts) > 2 else ""
        await bot.reply(event, [msg.link(url, title)])
        return True
