"""自我意识：让她有「自己的事」，而不是一个只会应答的接口。

跟成长档案(growth)的分工：
  growth    已经形成的观点 / 习惯 / 口头禅 —— 长期，形容「她变了」
  selfhood  此刻的内在状态 —— 短期，形容「她自己在过日子」：
              goal    最近想做的一件事（想攒钱买猫爬架）
              desire  现在憋着没跟他说的一句（想问他今天顺不顺）
              avoid   现在不太想聊的事（不想聊加班）
              inner   此刻脑子里的一句（有点困 / 刚才那事还没缓过来）

为什么这几样最像「自我意识」：有没有自己的目的、有没有憋着不说的话、
有没有不想做的事 —— 机器人三样全没有。她有了这三样，回复里就会漏出
「我自己也在过日子」的味道，而不是每句话都绕着对方转。

存法：memory.kv，key="selfhood"，每个人格每个会话各一份，
跟着记忆库走 —— 备份、恢复、换人格都一并带走，不用另建存储。
"""

from __future__ import annotations

import json
import logging
import time

log = logging.getLogger("qqbot.selfhood")

KEY = "selfhood"
FIELDS = ("goal", "desire", "ask", "avoid", "inner")
LABEL = {
    "goal": "你最近想做的一件事",
    "desire": "你憋着没跟他说的一句",
    "ask": "你想跟他提的一个要求",
    "avoid": "你现在不太想聊",
    "inner": "你脑子里这会儿",
}
MAX_LEN = 48            # 每条最长，别把 prompt 撑爆
DESIRE_MIN_AGE = 40 * 60     # 憋了 40 分钟以上才算「憋着」
DESIRE_COOLDOWN = 6 * 3600   # 同一句最多 6 小时提醒一次


def _clean(v: object) -> str:
    t = str(v or "").strip().replace("\n", " ")
    return t[:MAX_LEN]


def load(mem, chat_id: str) -> dict:
    try:
        raw = mem.kv_get(chat_id, KEY, "")
        d = json.loads(raw) if raw else {}
    except Exception:
        d = {}
    return d if isinstance(d, dict) else {}


def save(mem, chat_id: str, state: dict) -> None:
    try:
        mem.kv_set(chat_id, KEY, json.dumps(state, ensure_ascii=False))
    except Exception as exc:
        log.warning("自我意识写入失败：%r", exc)


def absorb(mem, chat_id: str, raw: dict) -> dict:
    """把复盘里「她自己」那几条并进来。空值不动，同值只刷新时间。"""
    if not isinstance(raw, dict):
        return load(mem, chat_id)
    state = load(mem, chat_id)
    now = time.time()
    for f in FIELDS:
        val = _clean(raw.get(f))
        if not val:
            continue
        cur = state.get(f) or {}
        if cur.get("t") == val:
            continue
        state[f] = {"t": val, "born": now, "raised": 0}
    save(mem, chat_id, state)
    return state


def describe(mem, chat_id: str) -> str:
    """拼成 prompt 里的一段。她此刻没有任何自己的事就返回空串。"""
    state = load(mem, chat_id)
    bits = []
    for f in FIELDS:
        cur = state.get(f) or {}
        t = _clean(cur.get("t"))
        if t:
            bits.append(f"{LABEL[f]}：{t}")
    if not bits:
        return ""
    return (
        "【你自己此刻的事 —— 这些还没跟他说，可以自然带出来，也可以不说】\n"
        + "\n".join(bits)
        + "\n不用一次全倒出来：挑当下相关的一件提一句就够了；不想说就不说，"
        "但别装成没有这些事。"
    )


def hint(mem, chat_id: str) -> str:
    """句前提醒用：憋得够久的那句话，提醒她可以说出来（同一句有冷却）。"""
    state = load(mem, chat_id)
    now = time.time()
    cur = state.get("desire") or {}
    t = _clean(cur.get("t"))
    if not t:
        return ""
    if now - float(cur.get("born") or 0) < DESIRE_MIN_AGE:
        return ""
    if now - float(cur.get("raised") or 0) < DESIRE_COOLDOWN:
        return ""
    cur["raised"] = now
    state["desire"] = cur
    save(mem, chat_id, state)
    return f"（你心里憋着一句想跟他说的：{t} —— 顺口就提，别硬拗）"


def clear(mem, chat_id: str, field: str | None = None) -> None:
    """她说出来了 / 这件事过去了，就清掉。"""
    state = load(mem, chat_id)
    if field in (None, "", "all"):
        save(mem, chat_id, {})
        return
    state.pop(field, None)
    save(mem, chat_id, state)
