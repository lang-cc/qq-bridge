"""掉线补偿：重连之后把没看到的话补回来。

为什么要它：机器人掉线（网络抖、QQ 抽风、服务重启）那段时间对方发的话
一条都收不到，回来之后聊天就像断片了 —— 她该知道刚才发生了什么。

做法：
  1. 心跳：在线时每 30 秒把「我还活着的时间」写进 data/conn.json
  2. 重连：算出这中间断了多久，只处理断线期间（以及上次已读之后）的消息
  3. 补齐：调 OneBot 的历史接口取最近几十条（端点不支持就静默跳过），
           取回来的他自己发的话写进记忆，然后让她回来补一句
"""

from __future__ import annotations

import json
import logging
import os
import time

log = logging.getLogger("qqbot.catchup")

PATH = "data/conn.json"


def load() -> dict:
    try:
        with open(PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save(d: dict) -> None:
    try:
        os.makedirs(os.path.dirname(PATH) or ".", exist_ok=True)
        tmp = PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, PATH)
    except Exception as exc:
        log.debug("写 conn.json 失败：%r", exc)


def touch(extra: dict | None = None) -> None:
    d = load()
    d["last_seen"] = time.time()
    if extra:
        d.update(extra)
    save(d)


def offline_seconds() -> float:
    d = load()
    since = float(d.get("last_seen") or 0)
    return 0.0 if not since else max(0.0, time.time() - since)


def _seg_text(seg) -> str:
    if isinstance(seg, str):
        return seg
    if not isinstance(seg, dict):
        return ""
    t = str(seg.get("type") or "")
    data = seg.get("data") or {}
    if t == "text":
        return str(data.get("text") or "")
    if t in ("image", "mface"):
        return "[图片]"
    if t == "face":
        return "[表情]"
    if t == "record":
        return "[语音]"
    if t == "video":
        return "[视频]"
    if t == "at":
        return ""
    return ""


def text_of(msg: dict) -> str:
    raw = msg.get("raw_message")
    if isinstance(raw, str) and raw.strip() and "[" not in raw[:2]:
        return raw.strip()
    segs = msg.get("message")
    if isinstance(segs, list):
        return "".join(_seg_text(s) for s in segs).strip()
    if isinstance(segs, str):
        return segs.strip()
    return ""


def pick_missed(resp, since: float, self_id: str, limit: int) -> list[dict]:
    """从历史接口的返回里挑出「断线期间他发的」消息。"""
    msgs = resp.get("messages") if isinstance(resp, dict) else resp
    if not isinstance(msgs, list):
        return []
    out: list[dict] = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        ts = float(m.get("time") or 0)
        if ts and ts < since:
            continue
        sender = (m.get("sender") or {}).get("user_id") or m.get("user_id")
        if self_id and str(sender) == str(self_id):
            continue
        txt = text_of(m)
        if not txt:
            continue
        out.append({"ts": ts, "text": txt[:120]})
    out.sort(key=lambda x: x["ts"])
    return out[-limit:]
