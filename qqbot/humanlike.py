"""真人感：把「一看就是机器人」的地方磨掉。

不调模型、不花钱，全在本地做四件事：
  1. 标点   短句不留句号，句中句号换空格，「嗯，」这种开头逗号去掉
  2. 半句   偶尔只留前半句，不每次都齐整
  3. 不回   极偶尔真的不回（已读，但没话）
  4. 连发   偶尔把一句话拆成两条发，中间停一下

配置在 autoreply.humanlike（网页「功能」页有开关，拨一下立即生效）。
"""

from __future__ import annotations

import random
import re

DEFAULTS = {
    "enabled": True,
    "no_period": True,      # 去掉句末句号、句中句号
    "short_chance": 0.12,   # 偶尔只回前半句
    "skip_chance": 0.03,    # 偶尔不回
    "burst_chance": 0.15,   # 偶尔拆两条发
}


def cfg_of(raw: dict | None) -> dict:
    c = dict(DEFAULTS)
    c.update({k: v for k, v in (raw or {}).items() if k in DEFAULTS})
    return c


def polish(text: str, no_period: bool = True) -> str:
    """去机器味标点。真人打短句不点句号，也不会写「嗯，」。"""
    t = (text or "").strip()
    if not t:
        return t
    if no_period:
        t = re.sub(r"[。．.]+$", "", t)                      # 句末句号不要
        t = re.sub(r"(?:[。．]\s*){2,}", "…", t)             # 「。。」→「…」
        t = t.replace("。", " ").replace("．", " ")           # 短句里点句号最假
        t = re.sub(r"[，,]", " ", t)                          # 逗号也用空格断
        t = re.sub(r"[、]", " ", t)
        t = re.sub(r"^([\u4e00-\u9fa5]{1,2}) ", r"\1 ", t)
        t = re.sub(r"[ \t]{2,}", " ", t)
        t = t.strip().rstrip(" 、；;")
    t = re.sub(r"[？?]{2,}", "？", t)                         # 疑问用单个问号
    t = re.sub(r"[！!]{2,}", "！", t)
    t = t.replace("?", "？")
    t = re.sub(r"[“”\"「」『』《》]", "", t)                  # 不打引号书名号
    t = t.replace("……", "…")
    return t.strip()


def shorten(text: str, chance: float) -> str:
    """偶尔只留前半句。只在有停顿、且前半句够长时砍。"""
    if chance <= 0 or random.random() >= chance:
        return text
    parts = re.split(r"(?<=[\s，,]|…)", (text or "").strip())
    first = (parts[0] if parts else "").strip()
    if len(first) >= 2 and len(first) < len(text):
        return first.rstrip("，,、 ")
    return text


def half(text: str, chance: float) -> str:
    """偶尔话说一半就停（真人常这样，尤其说理由的时候）。"""
    if chance <= 0 or random.random() >= chance:
        return text
    t = (text or "").strip()
    cuts = [m.start() for m in re.finditer(r"[ 　]", t) if 3 <= m.start() <= len(t) - 2]
    if not cuts:
        return text
    head = t[: random.choice(cuts)].strip()
    return head + ("…算了" if random.random() < 0.6 else "…")


def should_skip(chance: float) -> bool:
    return chance > 0 and random.random() < chance


def split_two(text: str) -> list[str]:
    """在最后一个停顿处拆成两条，两半都要够长，否则不拆。"""
    t = (text or "").strip()
    idx = max(t.rfind(" "), t.rfind("，"), t.rfind(","))
    if idx <= 0 or idx >= len(t) - 1:
        return [t]
    a, b = t[:idx].strip(" ，,"), t[idx + 1 :].strip(" ，,")
    if len(a) >= 4 and len(b) >= 4:      # 「老大」单独一条很怪，两半都得像句话
        return [a, b]
    return [t]


def want_burst(text: str, chance: float) -> bool:
    if chance <= 0 or random.random() >= chance:
        return False
    return len(split_two(text)) == 2
