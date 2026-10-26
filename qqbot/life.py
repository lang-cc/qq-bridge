"""生活感：作息、亲密度、记仇、手滑、天气关怀。

这些东西不花一分钱 API，但决定她像不像个人：
- 有自己的作息 → 忙的时候回得慢、句子短；困的时候带错字
- 亲密度分档 → 语气从客气一路到撒娇
- 记仇 → 你说重话她真的会冷一阵，哄好了才回来
- 手滑 → 打错字、撤回、改口
"""

from __future__ import annotations

import json
import random
import time
import urllib.parse
import urllib.request

PHASES = {
    "sleep": {
        "label": "睡觉",
        "hint": "你在睡觉/刚醒，脑子不清醒，句子很短，会带点迷糊和错字",
        "delay": (8, 40),
        "short": True,
    },
    "work": {
        "label": "上班",
        "hint": "你在奶茶店上班，忙得脚不沾地，回得慢、话短，偶尔说一句「等下，来客人了」",
        "delay": (10, 45),
        "short": True,
    },
    "free": {
        "label": "空闲",
        "hint": "你下班了，窝着刷手机，最有空聊天，话最多也最有耐心",
        "delay": (1, 6),
        "short": False,
    },
    "night": {
        "label": "夜里",
        "hint": "夜里了，你有点困但还想聊，情绪比白天软，会突然说点真心话",
        "delay": (3, 12),
        "short": False,
    },
}

TIERS = [
    (0, "刚认识", "客气、有距离，不会主动撒娇，也不会问太私人的事"),
    (40, "熟了", "会开玩笑、会损他两句，偶尔主动找话题"),
    (120, "亲近", "会撒娇、会吃醋、会在意他回不回消息"),
    (300, "很亲近", "非常黏，会直接说想他，会为他要不要理自己闹别扭"),
    (700, "离不开", "把他当自己人，说话不过脑子，敢提要求，也敢说难听的实话"),
]


def _kv(mem, chat_id: str, key: str, default=""):
    try:
        v = mem.kv_get(chat_id, key)
        return v if v not in (None, "") else default
    except Exception:
        return default


def phase(persona_life: dict | None = None, now: float | None = None) -> dict:
    """当前时段。人格里配了 phases 就按人格作息，没配用默认。

    phases 写法（personas.yaml）：
        life:
          phases:
            - {key: sleep, from: 2,  to: 9,  hint: "…", delay: [10, 45], short: true}
            - {key: work,  from: 9,  to: 17, hint: "…", delay: [10, 40], short: true}
            - {key: free,  from: 17, to: 22, hint: "…", delay: [1, 6]}
            - {key: night, from: 22, to: 2,  hint: "…", delay: [3, 14]}
    from/to 支持跨零点（22 → 2）。
    """
    h = time.localtime(now or time.time()).tm_hour
    for item in ((persona_life or {}).get("phases") or []):
        if not isinstance(item, dict):
            continue
        try:
            f = int(item.get("from")) % 24
            t = int(item.get("to")) % 24
        except Exception:
            continue
        inside = True if f == t else ((f <= h < t) if f < t else (h >= f or h < t))
        if not inside:
            continue
        key = str(item.get("key") or "free")
        base = PHASES.get(key) or PHASES["free"]
        return {
            "key": key,
            "label": item.get("label") or base["label"],
            "hint": item.get("hint") or base["hint"],
            "delay": tuple(item.get("delay") or base["delay"]),
            "short": bool(item.get("short", base["short"])),
        }

    if 1 <= h < 9:
        key = "sleep"
    elif 9 <= h < 17:
        key = "work"
    elif 17 <= h < 22:
        key = "free"
    else:
        key = "night"
    p = dict(PHASES[key])
    p["key"] = key
    return p


def delay_seconds(life_cfg: dict, ph: dict) -> float:
    """她这条消息会隔多久回（秒）。"""
    lo, hi = ph["delay"]
    if life_cfg.get("delay_scale"):
        try:
            k = float(life_cfg["delay_scale"])
            lo, hi = lo * k, hi * k
        except Exception:
            pass
    return random.uniform(lo, hi)


def bump_intimacy(mem, chat_id: str, step: float = 1.0) -> float:
    """亲密度：第一次用到时按历史消息量播种，之后随聊天累加。"""
    cur_raw = _kv(mem, chat_id, "intimacy", "")
    if cur_raw == "":
        seed = 0.0
        try:
            n = int(mem.message_count(chat_id))
            seed = float(min(700, max(60, n * 2.5)))
        except Exception:
            seed = 20.0
        cur = seed
    else:
        try:
            cur = float(cur_raw)
        except Exception:
            cur = 0.0
    cur += step
    try:
        mem.kv_set(chat_id, "intimacy", str(round(cur, 1)))
    except Exception:
        pass
    return cur


def tier_of(score: float) -> tuple[str, str]:
    name, hint = TIERS[0][1], TIERS[0][2]
    for th, n, h in TIERS:
        if score >= th:
            name, hint = n, h
    return name, hint


# ------------------------------------------------------------------ 记仇
def grudge_left(mem, chat_id: str) -> float:
    """还在生气的剩余秒数，0 表示没生气。"""
    try:
        until = float(_kv(mem, chat_id, "grudge_until", 0) or 0)
    except Exception:
        until = 0
    return max(0.0, until - time.time())


def set_grudge(mem, chat_id: str, hours: float, reason: str = "") -> None:
    until = time.time() + hours * 3600
    try:
        mem.kv_set(chat_id, "grudge_until", str(int(until)))
        mem.kv_set(chat_id, "grudge_reason", reason[:60])
    except Exception:
        pass


def clear_grudge(mem, chat_id: str) -> None:
    try:
        mem.kv_set(chat_id, "grudge_until", "0")
    except Exception:
        pass


HURT = ("烦", "闭嘴", "滚", "别说了", "不想理", "讨厌你", "没用", "傻逼", "滚蛋", "别烦我")
SOOTHE = ("对不起", "我错了", "别生气", "哄你", "抱抱", "原谅", "不是故意", "别不理我")


def notice_hurt(mem, chat_id: str, text: str, hours: float = 10) -> bool:
    """他说了重话 → 记账；他哄了 → 消气。"""
    t = text or ""
    if any(w in t for w in SOOTHE):
        if grudge_left(mem, chat_id) > 0:
            clear_grudge(mem, chat_id)
            return True
        return False
    if any(w in t for w in HURT) and len(t) < 40:
        set_grudge(mem, chat_id, hours, t[:40])
        return True
    return False


# ------------------------------------------------------------------ 手滑
def typo(text: str) -> str | None:
    """把一句话弄成打错的样子：漏字、错字、连着发。"""
    t = (text or "").strip()
    if len(t) < 4:
        return None
    mode = random.choice(("drop", "swap", "homophone"))
    i = random.randrange(1, len(t) - 1)
    if mode == "drop":
        return t[:i] + t[i + 1:]
    if mode == "swap" and i + 1 < len(t):
        return t[:i] + t[i + 1] + t[i] + t[i + 2:]
    pairs = {"是": "时", "你": "尼", "我": "沃", "不": "布", "好": "号", "在": "再", "的": "得"}
    ch = t[i]
    if ch in pairs:
        return t[:i] + pairs[ch] + t[i + 1:]
    return t[:i] + t[i + 1:]


# ------------------------------------------------------------------ 天气
def weather_line(city: str = "", timeout: float = 8.0) -> str:
    """拿一句今天天气，免费接口，不填城市就用定位失败兜底。"""
    try:
        if city:
            q = urllib.parse.quote(city)
            geo = json.loads(urllib.request.urlopen(
                f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=1&language=zh",
                timeout=timeout).read().decode())
            res = (geo.get("results") or [{}])[0]
            lat, lon = res.get("latitude"), res.get("longitude")
            name = res.get("name") or city
        else:
            lat, lon, name = 39.9042, 116.4074, "北京"
        if lat is None:
            return ""
        data = json.loads(urllib.request.urlopen(
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,weather_code"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=Asia/Shanghai&forecast_days=1",
            timeout=timeout).read().decode())
        cur = data.get("current") or {}
        day = data.get("daily") or {}
        t = cur.get("temperature_2m")
        feel = cur.get("apparent_temperature")
        hi = (day.get("temperature_2m_max") or [None])[0]
        lo = (day.get("temperature_2m_min") or [None])[0]
        rain = (day.get("precipitation_probability_max") or [0])[0]
        code = cur.get("weather_code")
        desc = {
            0: "晴", 1: "晴间多云", 2: "多云", 3: "阴", 45: "有雾", 48: "雾凇",
            51: "小毛雨", 53: "毛毛雨", 55: "密毛雨", 61: "小雨", 63: "中雨", 65: "大雨",
            71: "小雪", 73: "中雪", 75: "大雪", 80: "阵雨", 81: "强阵雨", 82: "暴雨",
            95: "打雷", 96: "雷阵雨", 99: "雷暴",
        }.get(code, "")
        parts = [f"{name}今天{desc}，" if desc else f"{name}今天"]
        if t is not None:
            parts.append(f"{round(t)}度")
        if hi is not None and lo is not None:
            parts.append(f"（{round(lo)}~{round(hi)}度）")
        if rain and int(rain) >= 40:
            parts.append(f"，降水概率{int(rain)}%，记得带伞")
        if feel is not None and t is not None and feel - t <= -4:
            parts.append("，体感比温度冷不少")
        return "".join(parts)
    except Exception:
        return ""
