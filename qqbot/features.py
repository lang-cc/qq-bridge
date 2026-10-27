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
    ("llm",       "聊天", "AI 回复",     "调模型回话。关掉她只会用兜底回复", ("llm", "enabled")),
    ("memory",    "聊天", "长期记忆",   "记总结、记事实、写日记。关掉只记得当前几条上下文", ("memory", "enabled")),
    ("persona",   "聊天", "人格切换",   "允许用「切换人格 阿糖」换人，记忆各自独立", ("persona", "enabled")),
    ("mood",      "像人", "心情",       "她的情绪状态，影响语气和表情包挑选", ("mood", "enabled")),
    ("intimacy",  "像人", "好感度",     "按聊天慢慢涨好感，分陌生/眼熟/亲近几档", ("intimacy", "enabled")),
    ("life",      "像人", "生活感",     "作息、已读不回、半夜不爱回话", ("life", "enabled")),
    ("grudge",    "像人", "记仇",       "被怼了记几个小时，之后说话带刺", ("grudge", "enabled")),
    ("diary",     "像人", "日记",       "每天睡前写一段只有她自己知道的日记", ("diary", "enabled")),
    ("stickers",  "表达", "表情包",     "配图、斗图（stickers 目录里的图）", ("stickers", "enabled")),
    ("tts",       "表达", "语音",       "偶尔发语音（edge / 火山 TTS）", ("tts", "enabled")),
    ("image",     "表达", "画图",       "偶尔自己画一张图发出来", ("image", "enabled")),
    ("web",       "上网", "网页搜索",   "发链接、问事情时上网查一下", ("web", "enabled")),
    ("bilibili",  "上网", "B站热搜",    "聊到热门/视频时去 B 站看看", ("web", "bilibili")),
    ("video",     "上网", "视频分享",   "分享视频", ("video", "enabled")),
    ("douyin",    "上网", "抖音",       "抓抖音推荐页分享（走无头浏览器，比较重）", ("douyin", "enabled")),
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
