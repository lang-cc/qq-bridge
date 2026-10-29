"""「功能」清单：她身上的每一项能力，一个一个开关。

跟 qqbot/plugin_info.py 里的「指令插件」是两层东西：

    指令插件  = qqbot/plugins/*.py 文件级的（help / ping / echo / 截屏 …）
    功能      = 引擎里的能力（心情 / 好感度 / 表情包 / 语音 / 主动开聊 …）

功能开关落在 config.yaml 的 autoreply 段里，跟网页配置台「模型」「行为」页写的是同一份配置，
所以改完立即生效，重启也还在。
"""

from __future__ import annotations

from typing import Any

# id, 分组, 中文名, 说明, 配置路径
FEATURES: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    # "AI 回复"(llm.enabled) 不在这里列：它默认就是开的，关掉等于让她变哑巴，
    # 属于运维开关而不是"功能"，要改就改 config.yaml 的 autoreply.llm.enabled
    ("memory",    "聊天", "长期记忆",   "记总结、记事实、写日记。关掉只记得当前几条上下文", ("memory", "enabled")),
    ("catchup",   "聊天", "掉线补偿",   "掉线重连后把没看到的话读回来，并接一句", ("catchup", "enabled")),
    ("mood",      "像人", "心情",       "她的情绪状态，影响语气和表情包挑选", ("mood", "enabled")),
    ("intimacy",  "像人", "好感度",     "按聊天慢慢涨好感，分陌生/眼熟/亲近几档", ("intimacy", "enabled")),
    ("life",      "像人", "生活感",     "作息、已读不回、半夜不爱回话", ("life", "enabled")),
    ("grudge",    "像人", "记仇",       "被怼了记几个小时，之后说话带刺", ("grudge", "enabled")),
    ("diary",     "像人", "日记",       "每天睡前写一段只有她自己知道的日记", ("diary", "enabled")),
    ("selfhood",  "像人", "自我意识",   "她有自己的目的、憋着没说的一句话、不想聊的事；会主动提起，也能拒绝", ("selfhood", "enabled")),
    ("loops",     "像人", "惦记你的事", "你说过还没结果的事（面试/体检/等他回话），过一两天她真的会来问一句", ("loops", "enabled")),
    ("misread",   "像人", "会没听懂",   "偶尔理解偏，或者直接问「啥意思」——不是每次都秒懂", ("misread", "enabled")),
    ("world",     "像人", "生活细节",   "固定的城市/店名/室友/猫，跨天一致，不会每次换一个", ("world", "enabled")),
    ("humor",     "像人", "会开玩笑",   "接梗、损人、夸张吐槽，笑点不解释", ("humor", "enabled")),
    ("pacing",    "像人", "回复速度",   "回话间隔在 2–15 秒之间随机（区间在 config.yaml 的 reply_delay 改）", ("reply_delay", "enabled")),
    ("ignore",    "像人", "会不理你",   "偶尔不回话；把他惹生气了基本就不理你了", ("ignore", "enabled")),
    ("stickers",  "表达", "表情包",     "配图、斗图（stickers 目录里的图）", ("stickers", "enabled")),
    ("tts",       "表达", "语音",       "偶尔发语音（edge / 火山 TTS）", ("tts", "enabled")),
    ("image",     "表达", "画图",       "偶尔自己画一张图发出来", ("image", "enabled")),
    ("vision",    "表达", "看图",       "你发的图、截图她都看得懂，能接着聊", ("vision", "enabled")),
    ("mention",   "表达", "@人",        "群里说话偶尔 @ 你一下", ("mention", "enabled")),
    ("poke",      "表达", "戳一戳",     "想引起你注意时戳你一下", ("poke", "enabled")),
    ("qzone",     "表达", "发说说",     "每天到点自己写一条 QQ 空间说说", ("qzone", "enabled")),
    ("share",     "主动", "主动分享",   "刷到好玩的、自己办成的事，会主动发给你看", ("share", "enabled")),
    ("ask",       "主动", "提要求",     "想要什么直接跟你说，不等你问", ("ask", "enabled")),
    ("wander",    "上网", "自主上网",   "自己上网翻热梗和好玩的东西，聊天里会顺口提起", ("wander", "enabled")),
    ("proactive", "主动", "主动开聊",   "隔一阵子自己找你说话", ("proactive", "enabled")),
    ("whitelist", "安全", "白名单",     "只回名单里的人（关掉所有人私聊都会回）", ("whitelist", "enabled")),
)

GROUP_ORDER = ("聊天", "像人", "表达", "上网", "主动", "安全")


def _dig(cfg: dict, path: tuple[str, ...]) -> Any:
    cur: Any = cfg
    for k in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _plant(cfg: dict, path: tuple[str, ...], value: Any) -> None:
    cur = cfg
    for k in path[:-1]:
        nxt = cur.get(k)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[k] = nxt
        cur = nxt
    cur[path[-1]] = value


def by_id(fid: str):
    for f in FEATURES:
        if f[0] == fid:
            return f
    return None


def build(cfg: dict) -> list[dict]:
    """cfg = autoreply 段（引擎已经合并过默认值的那份最好）。"""
    out: list[dict] = []
    for fid, group, name, desc, path in FEATURES:
        val = _dig(cfg or {}, path)
        out.append({
            "id": fid,
            "group": group,
            "name": name,
            "desc": desc,
            "path": ".".join(path),
            "enabled": bool(val) if val is not None else True,
        })
    out.sort(key=lambda x: (GROUP_ORDER.index(x["group"]) if x["group"] in GROUP_ORDER else 99, x["name"]))
    return out


def apply(cfg: dict, fid: str, enabled: bool) -> dict:
    """把开关写进配置字典（调用方负责落盘和通知引擎）。"""
    f = by_id(fid)
    if not f:
        raise KeyError(fid)
    _plant(cfg, f[4], bool(enabled))
    return cfg
