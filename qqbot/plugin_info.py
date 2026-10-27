"""插件清单（给网页配置台的「功能」标签用）。

老插件的说明从注册时的 desc 推出来，名字和一句话简介在这里维护：
新加一个插件 = 在 qqbot/plugins 里放文件 + 在 legacy_bridge.LEGACY_PLUGINS 里加名字
（NICE 里补一行就更友好，不补也能显示）。
"""

from __future__ import annotations

from typing import Any

from . import toggles

# 插件 id → (中文名, 一句话说明)
NICE: dict[str, tuple[str, str]] = {
    "qqbot.plugins.companion": ("陪聊引擎", "记忆 / 情绪 / 人格 / 表情包 / 主动开聊 —— 她本人"),
    "qqbot.plugins.help": ("帮助", "help / 菜单 / 状态：列出所有指令"),
    "qqbot.plugins.ping": ("心跳", "ping → pong，测机器人在不在"),
    "qqbot.plugins.echo": ("复读", "echo 内容：原样复读"),
    "qqbot.plugins.send_tools": ("发东西", "截屏 / 网页截屏 / 发图 / 发文件 / 发语音 / 发链接"),
    "qqbot.plugins.rules_demo": ("正则演示", "谁是管理 / 打卡（教怎么写正则插件）"),
    "nb.plugins.nb_sys": ("框架指令", "/nb、/nbhelp：NoneBot 自带的指令"),
}

# 想让「插件」页顺序稳定，按这个来
ORDER = list(NICE.keys())


def build(router: Any) -> list[dict]:
    """按插件分组列出：指令、说明、开关状态、处理器数量。"""
    groups: dict[str, dict] = {}
    for h in list(getattr(router, "handlers", []) or []):
        pid = h.plugin or "unknown"
        g = groups.setdefault(pid, {"id": pid, "commands": [], "descs": [], "handlers": 0})
        g["handlers"] += 1
        if getattr(h, "command", None):
            g["commands"].append(h.command)
        elif getattr(h, "regex", None):
            g["commands"].append("正则 " + h.regex.pattern)
        d = getattr(h, "desc", "") or ""
        if d and d not in g["descs"]:
            g["descs"].append(d)

    # nb_sys 是框架原生插件，不在老路由里，手工补一条
    groups.setdefault("nb.plugins.nb_sys", {
        "id": "nb.plugins.nb_sys",
        "commands": ["/nb", "/nbhelp"],
        "descs": ["看框架状态 / 已加载插件"],
        "handlers": 2,
    })

    out: list[dict] = []
    for pid, g in groups.items():
        name, desc = NICE.get(pid, (pid.rsplit(".", 1)[-1], ""))
        if not desc:
            desc = "、".join(g["descs"][:3])
        cmds = [c for c in dict.fromkeys(g["commands"])]
        out.append({
            "id": pid,
            "name": name,
            "desc": desc,
            "commands": cmds[:20],
            "count": g["handlers"],
            "enabled": toggles.is_enabled(pid),
            "core": pid in ("qqbot.plugins.companion",),  # 关掉等于她不说话了，页面要提醒
        })

    def key(item: dict) -> tuple[int, str]:
        try:
            return (ORDER.index(item["id"]), "")
        except ValueError:
            return (len(ORDER), item["id"])

    return sorted(out, key=key)
