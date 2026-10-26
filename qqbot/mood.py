"""心情模型：两个维度 + 随时间自然回落，被对话影响。

valence 心情好坏 [-1, 1]，energy 精力 [0, 1]。存进 memory.state，重启不丢。
"""

from __future__ import annotations

import time

# 关键词 -> (valence 变化, energy 变化)
KEYWORD_HINTS = {
    "累": (-0.15, -0.20),
    "烦": (-0.20, -0.10),
    "难过": (-0.30, -0.10),
    "哭": (-0.30, -0.05),
    "生气": (-0.25, 0.05),
    "加班": (-0.20, -0.20),
    "哈哈": (0.15, 0.10),
    "开心": (0.25, 0.10),
    "好耶": (0.20, 0.05),
    "喜欢你": (0.30, 0.10),
    "晚安": (0.05, -0.15),
    "在吗": (0.05, 0.05),
    "想你": (0.25, 0.05),
}

DEFAULT = {"valence": 0.1, "energy": 0.6, "ts": 0.0}


def load(raw: dict, now: float | None = None) -> dict:
    now = now or time.time()
    state = dict(DEFAULT)
    if isinstance(raw, dict):
        for k in ("valence", "energy", "ts"):
            if k in raw:
                try:
                    state[k] = float(raw[k])
                except Exception:
                    pass
    return decay(state, now)


def decay(state: dict, now: float | None = None) -> dict:
    """心情半衰期约 6 小时，精力按 10 小时回落到 0.5。"""
    now = now or time.time()
    last = float(state.get("ts") or 0) or now
    hours = max(0.0, (now - last) / 3600.0)
    v = float(state.get("valence", 0.1))
    e = float(state.get("energy", 0.6))
    if hours:
        v *= 0.5 ** (hours / 6.0)
        e = 0.5 + (e - 0.5) * (0.5 ** (hours / 10.0))
    return {"valence": round(v, 3), "energy": round(e, 3), "ts": now}


def nudge(state: dict, text: str) -> dict:
    v = float(state.get("valence", 0.1))
    e = float(state.get("energy", 0.6))
    for kw, (dv, de) in KEYWORD_HINTS.items():
        if kw in (text or ""):
            v += dv
            e += de
    v = max(-1.0, min(1.0, v))
    e = max(0.05, min(1.0, e))
    return {"valence": round(v, 3), "energy": round(e, 3), "ts": time.time()}


def label(state: dict) -> str:
    v = float(state.get("valence", 0))
    e = float(state.get("energy", 0.5))
    mood = "挺开心" if v > 0.4 else "还行" if v > 0.05 else "有点低落" if v > -0.4 else "很难受"
    body = "精神很足" if e > 0.75 else "正常" if e > 0.4 else "有点困/没劲"
    return f"{mood}，{body}"


def describe(state: dict) -> str:
    """塞进 prompt 的一句话自述。"""
    return (
        f"你现在的心情：{label(state)}（情绪值 {state.get('valence')} / 精力 {state.get('energy')}）。"
        "心情要体现在语气里，但别直接报数值。"
    )
