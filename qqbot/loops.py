"""悬案（open loops）：她惦记着、还没问出口的事。

真人最像人的动作不是回得漂亮，是**正聊着别的，突然问一句「对了你那个面试咋样了」**。
机器人永远不会问 —— 因为它没有"挂着没放下的事"。

数据从哪来：不额外花一次 API。复盘（REFLECT_PROMPT）本来每几轮就调一次模型，
顺手让它把这批对话里「他说过但还没结果的事」列出来（面试、体检、等他回话、
答应要办的事、要见的人）。存进 memory 的 loop 表，到点了由主动消息去问，
平时也在 system 里挂一句，聊天沾边了会自己提。

三条纪律，不然就变成"查户口"：
  1. 同一个话题最多问 3 次，每次隔 2 天（memory.loop_touch 负责推后）
  2. 只挂「有具体下落可问」的事，泛泛的"他最近很累"不算
  3. 超过 45 天没结果的直接丢（隔俩月再问「那个面试」很怪）
"""

from __future__ import annotations

import logging
import time

log = logging.getLogger("qqbot.loops")

KEY = "loops"     # 配置段名 autoreply.loops

DEFAULTS = {
    "enabled": True,
    "max_ask": 3,        # 同一件事最多追问几次
    "drop_days": 45,     # 超过这么多天还没结果就丢掉
    "max_prompt": 2,     # system 里最多挂几件（挂多了她会满脑子都是事）
    "min_hours": 6,      # 登记后至少隔这么久才第一次问，别刚说完就追
}

# 模型说「1 小时」和「1 天」都得能理解；给个合理区间，别让它把 due 写成十年前
MIN_DAYS, MAX_DAYS = 0.04, 40.0


def cfg_of(raw: dict | None) -> dict:
    c = dict(DEFAULTS)
    c.update({k: v for k, v in (raw or {}).items() if k in DEFAULTS})
    return c


def _num(v, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return default


def absorb(mem, chat_id: str, items, done=None, cfg: dict | None = None) -> dict:
    """把复盘里抽出来的悬案写进去。items=[{thing, detail, due_days}]，done=["面试", ...]。"""
    c = cfg_of(cfg)
    if not c.get("enabled", True):
        return {"added": 0, "closed": 0}
    closed = 0
    for t in done or []:
        try:
            closed += mem.loop_close(chat_id, str(t))
        except Exception as exc:
            log.debug("关闭悬案失败：%r", exc)
    added = 0
    now = time.time()
    for it in items or []:
        if not isinstance(it, dict):
            continue
        thing = str(it.get("thing") or "").strip()[:40]
        if len(thing) < 2:
            continue
        detail = str(it.get("detail") or "").strip()[:120]
        days = _num(it.get("due_days"), 2.0)
        days = max(MIN_DAYS, min(MAX_DAYS, days))
        # 至少隔 min_hours 再问，避免"刚说完明天面试，五分钟后问她面试咋样"
        days = max(days, _num(c.get("min_hours"), 6) / 24.0)
        try:
            if mem.loop_add(chat_id, thing, detail, now + days * 86400):
                added += 1
        except Exception as exc:
            log.debug("登记悬案失败：%r", exc)
    if added or closed:
        log.info("悬案更新[%s]：新增/更新 %d 件，结掉 %d 件", chat_id, added, closed)
    return {"added": added, "closed": closed}


def due(mem, chat_id: str, cfg: dict | None = None) -> dict | None:
    """到点该问的一件（主动消息用）。"""
    c = cfg_of(cfg)
    if not c.get("enabled", True):
        return None
    try:
        return mem.loop_due(chat_id, max_ask=int(c.get("max_ask") or 3))
    except Exception as exc:
        log.debug("读悬案失败：%r", exc)
        return None


def mark_asked(mem, loop: dict, cfg: dict | None = None) -> None:
    try:
        mem.loop_touch(int(loop.get("id") or 0))
    except Exception as exc:
        log.debug("悬案计数失败：%r", exc)


def open_loops(mem, chat_id: str, limit: int = 20) -> list[dict]:
    try:
        return mem.loop_open(chat_id, limit)
    except Exception:
        return []


def describe(mem, chat_id: str, cfg: dict | None = None) -> str:
    """system 里挂一小段：她心里惦记着的事。

    只在「快到期」或「刚到期」时挂 —— 挂一堆没到点的事，她会句句都想岔过去问。
    """
    c = cfg_of(cfg)
    if not c.get("enabled", True):
        return ""
    items = open_loops(mem, chat_id, 12)
    if not items:
        return ""
    now = time.time()
    soon = now + 12 * 3600
    pick = [x for x in items if x["due_at"] <= soon][: int(c.get("max_prompt") or 2)]
    if not pick:
        return ""
    lines = []
    for x in pick:
        d = f"（{x['detail']}）" if x.get("detail") else ""
        lines.append(f"- {x['thing']}{d}")
    return (
        "【你心里还惦记着他这几件事（还没问出结果）】\n"
        + "\n".join(lines)
        + "\n聊天正好沾边就顺口问一句，像突然想起来那样；不沾边就别硬扯，"
        "别为了问而问，也别一次把这些全倒出来。"
    )


def ask_instruction(loop: dict, hhmm: str) -> str:
    """主动消息的指令：问她惦记的那件事。"""
    thing = str(loop.get("thing") or "").strip()
    detail = str(loop.get("detail") or "").strip()
    tail = f"（你记得的是：{detail}）" if detail else ""
    return (
        f"现在是 {hhmm}，没人说话。你手边有事在干，忽然想起他之前提过的一件事：{thing}{tail}。"
        "用你自己的口吻问一句结果，就像突然想起来那样 —— 不要解释你为什么问、"
        "不要说「我突然想起来问一下」这种书面话、别客套。"
        "一句话，20 字以内；可以顺手带一句你此刻在干什么。不要问「在吗」。"
    )
