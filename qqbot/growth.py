"""人设成长档案：让角色从对话里慢慢长出自己的观点、习惯和口头禅。

跟「记忆」的区别：
    记忆(memory)   记的是**事**：他说过什么、约定、喜好
    成长(growth)   改的是**她自己**：她现在怎么看事、最近什么习惯、嘴上爱说什么

存法：data/growth/<角色id>_<会话id>.json
    opinions  观点（对不同事情的立场，越长越稳）
    habits    最近的生活习惯（熬夜、吃夜宵、迷上某部剧）
    voice     口头禅 / 语气（从她真说过的话里提炼）
    self      对自己的认知（比如「我其实嘴硬」）
每条带 hits（被引用次数）和 born（产生时间），太久没用会淡出，避免人设越堆越乱。
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

log = logging.getLogger("qqbot.growth")

MAX_PER_KIND = 12          # 每类最多留几条
MAX_AGE_DAYS = 120         # 超过这个时间没被用过就淡出


def _path(root: str | Path, pid: str, chat_id: str) -> Path:
    folder = Path(root) / "growth"
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w.-]", "_", f"{pid}_{chat_id}")
    return folder / f"{safe}.json"


def load(root: str | Path, pid: str, chat_id: str) -> dict:
    p = _path(root, pid, chat_id)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("成长档案读取失败 %s：%r", p, exc)
        return {}


def save(root: str | Path, pid: str, chat_id: str, data: dict) -> None:
    p = _path(root, pid, chat_id)
    try:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as exc:
        log.warning("成长档案写入失败 %s：%r", p, exc)


def _merge_items(old: list[dict], new: list[str], kind: str) -> list[dict]:
    """新条目并进旧档案：重复的只加 hits，别的按时间淘汰。"""
    now = time.time()
    items = [dict(x) for x in (old or []) if isinstance(x, dict)]
    for raw in new or []:
        text = str(raw or "").strip()
        if len(text) < 2 or len(text) > 60:
            continue
        hit = next((x for x in items if x.get("text") == text), None)
        if hit:
            hit["hits"] = int(hit.get("hits") or 1) + 1
            hit["ts"] = now
            continue
        items.append({"text": text, "hits": 1, "ts": now, "kind": kind})
    # 淡出：太老又没被再用过的丢掉
    cutoff = now - MAX_AGE_DAYS * 86400
    items = [x for x in items if float(x.get("ts") or now) >= cutoff]
    # 排序：用得多的优先，其次新的
    items.sort(key=lambda x: (int(x.get("hits") or 1), float(x.get("ts") or 0)), reverse=True)
    return items[:MAX_PER_KIND]


def absorb(root: str | Path, pid: str, chat_id: str, fresh: dict) -> dict:
    """把复盘得到的 self 数据并进档案，返回合并后的档案。"""
    data = load(root, pid, chat_id)
    for kind in ("opinions", "habits", "voice", "self"):
        if kind in fresh:
            data[kind] = _merge_items(data.get(kind) or [], fresh.get(kind) or [], kind)
    data["updated"] = time.time()
    save(root, pid, chat_id, data)
    return data


def describe(data: dict, limit: int = 3) -> str:
    """拼成能塞进提示词的一段话；没内容就返回空串。"""
    if not data:
        return ""
    bits: list[str] = []
    for kind, label in (("self", "你怎么看自己"), ("opinions", "你现在的看法"),
                        ("habits", "你最近的状态"), ("voice", "你嘴上常挂的")):
        items = [x.get("text") for x in (data.get(kind) or [])[:limit] if x.get("text")]
        if items:
            bits.append(f"{label}：" + "；".join(items))
    return "【你自己长出来的东西（不是设定，是聊出来的）】\n" + "\n".join(bits) if bits else ""


def brief(data: dict, limit: int = 2) -> str:
    """极简版：塞进句前提醒用（那类型号不认 system，只能贴在话前面）。"""
    if not data:
        return ""
    bits: list[str] = []
    for kind in ("self", "opinions", "voice"):
        items = [x.get("text") for x in (data.get(kind) or [])[:limit] if x.get("text")]
        if items:
            bits.extend(items)
    if not bits:
        return ""
    return "（你心里本来就有这些想法：" + "；".join(bits[:3]) + "）"


def stats(root: str | Path, pid: str, chat_id: str) -> dict:
    data = load(root, pid, chat_id)
    out = {"updated": data.get("updated")}
    for kind in ("opinions", "habits", "voice", "self"):
        out[kind] = len(data.get(kind) or [])
    return out
