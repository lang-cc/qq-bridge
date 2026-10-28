"""自主上网瞎逛：好奇心驱动，不是「功能触发」。

每过几小时，她自己挑点东西上网翻一翻 —— 不调模型，只发一两个请求：

  两路来源
    curiosity  她自己在想的事（selfhood 的目的 / 脑子里想的 / 憋着的话、成长档案的观点）
    hot        网络热梗 / 热门（B 站热门、搜「最近很火的梗」）
  结果存哪    memory.kv 的 wander（每人格每会话一份，跟记忆库一起备份恢复）
  怎么表现    回复时 prompt 里出现【你刚自己看到的】，她想提就顺口提一句；
              新鲜又没分享过的，主动开聊时会拿它开口 —— 就像朋友刷到好玩的甩给你

为什么不做成「网页搜索」开关：那是等人来问才去查，是被动工具；
这个是她自己刷到东西回来说，是主动生活。
"""

from __future__ import annotations

import json
import logging
import random
import re
import time

log = logging.getLogger("qqbot.wander")

KEY = "wander"
KEEP = 3                   # 只留最近几条，别把 kv 撑大
MAX_AGE_HOURS = 8          # 超过这么久就不再提，翻篇了
SHARE_MAX_HOURS = 3        # 主动分享只发新鲜的

# 她「没别的事可看」时的日常好奇心
FALLBACK = (
    "猫爬架 怎么挑",
    "熬夜 掉头发 真的吗",
    "奶茶 新品",
    "打雷 为什么先看到闪电",
    "二手自行车 多少钱",
    "冬天手冻 怎么办",
    "附近 好吃 面馆",
    "手机 电池 不耐用",
)
# 热梗这条路的搜索词
HOT_QUERIES = (
    "最近很火的梗 是什么意思",
    "今天 网络热梗",
    "这两天 大家都在说 什么梗",
)

# 这些词当关键词搜不出东西，只会搜到百科词条
STOP = {
    "有点", "有点困", "今天", "明天", "最近", "现在", "一个", "什么", "怎么", "但是", "因为",
    "所以", "觉得", "感觉", "自己", "我们", "他们", "东西", "事情", "时候", "真的", "还是",
    "不想", "想买", "想攒", "攒钱", "眼睛", "顺不顺", "不知道", "可能", "应该",
}
# 搜出来是这类结果等于没搜到
JUNK = ("百科", "词典", "字典", "汉典", "汉语", "拼音", "是什么意思", "翻译")
VERBY = "想买攒要会得个把被很太也还的了"


# ---------------------------------------------------------------- 存 / 取
def _load(mem, chat_id: str) -> dict:
    try:
        raw = mem.kv_get(chat_id, KEY, "")
        d = json.loads(raw) if raw else {}
    except Exception:
        d = {}
    if not isinstance(d, dict):
        d = {}
    if "items" not in d:            # 兼容旧格式（单条 {q,title,...}）
        old = {k: d.get(k) for k in ("q", "title", "digest", "url", "ts") if d.get(k)}
        d = {"items": [dict(old, kind="curiosity")] if old.get("title") else []}
    return d


def _save(mem, chat_id: str, d: dict) -> None:
    items = sorted(d.get("items") or [], key=lambda x: float(x.get("ts") or 0), reverse=True)[:KEEP]
    try:
        mem.kv_set(chat_id, KEY, json.dumps({"items": items}, ensure_ascii=False))
    except Exception as exc:
        log.warning("瞎逛结果存不进记忆：%r", exc)


def _add(mem, chat_id: str, item: dict) -> dict:
    d = _load(mem, chat_id)
    d["items"] = [x for x in (d.get("items") or []) if x.get("title") != item.get("title")]
    d["items"].append(item)
    _save(mem, chat_id, d)
    return item


# ---------------------------------------------------------------- 找词
def _seed(mem, chat_id: str, root: str, pid: str) -> str:
    """从她最近在想的东西里挑一句当搜索词。"""
    from . import growth, selfhood

    cands: list[str] = []
    try:
        st = selfhood.load(mem, chat_id)
        for f in ("goal", "desire", "inner"):
            t = str((st.get(f) or {}).get("t") or "").strip()
            if t:
                cands.append(t)
    except Exception:
        pass
    try:
        g = growth.load(root, pid, chat_id)
        for kind in ("opinions", "habits"):
            for x in (g.get(kind) or [])[:3]:
                t = str(x.get("text") or "").strip()
                if t:
                    cands.append(t)
    except Exception:
        pass

    if cands:
        # 中文没空格，切出来的短词大多是垃圾（"不顺""爬架"）；整句当 query 更准
        raw = random.choice(cands)
        q = re.sub(r"[，。！？、…：；\s]+", " ", raw).strip()
        q = re.sub(r"^(我|你|他|她)", "", q).strip()[:16]
        if len(q) >= 3:
            return q
    return random.choice(FALLBACK)


def _junk(title: str) -> bool:
    t = str(title or "")
    return (not t) or any(k in t for k in JUNK)


def _pick(hits: list[dict], kind: str, q: str) -> dict | None:
    for h in hits or []:
        title = str(h.get("title") or "").strip()
        if _junk(title):
            continue
        return {
            "kind": kind,
            "q": q,
            "title": title[:60],
            "digest": str(h.get("snippet") or "").strip()[:90],
            "url": str(h.get("url") or ""),
            "ts": time.time(),
            "shared": False,
        }
    return None


# ---------------------------------------------------------------- 出门
async def _curiosity(mem, chat_id: str, root: str, pid: str) -> dict | None:
    from . import web_tools

    q = _seed(mem, chat_id, root, pid)
    for attempt in (1, 2):
        try:
            hits = await web_tools.web_search(q, limit=4)
        except Exception as exc:
            log.warning("瞎逛没连上：%r", exc)
            return None
        item = _pick(hits, "curiosity", q)
        if item:
            return item
        if attempt == 1:
            q = random.choice(FALLBACK)
    return None


async def _hot(mem, chat_id: str) -> dict | None:
    """热梗这条路：先看 B 站热门，不成再搜「最近很火的梗」。"""
    from . import web_tools

    try:
        bili = await web_tools.bilibili_hot(limit=6)
    except Exception:
        bili = []
    if bili:
        h = random.choice(bili)
        title = str(h.get("title") or "").strip()
        if title and not _junk(title):
            return {
                "kind": "hot",
                "q": "B 站热门",
                "title": title[:60],
                "digest": "",
                "url": str(h.get("url") or ""),
                "ts": time.time(),
                "shared": False,
            }
    q = random.choice(HOT_QUERIES)
    try:
        hits = await web_tools.web_search(q, limit=4)
    except Exception:
        return None
    return _pick(hits, "hot", q)


async def wander_once(mem, chat_id: str, root: str, pid: str) -> dict:
    """自己出门看一眼：一半看她自己好奇的，一半看网上在热闹什么。"""
    item = await _hot(mem, chat_id) if random.random() < 0.5 else await _curiosity(mem, chat_id, root, pid)
    if not item:
        item = await _curiosity(mem, chat_id, root, pid) or await _hot(mem, chat_id)
    if not item:
        return {}
    return _add(mem, chat_id, item)


# ---------------------------------------------------------------- 给模型看
def _fresh(item: dict, hours: float) -> bool:
    return time.time() - float(item.get("ts") or 0) <= hours * 3600


def describe(mem, chat_id: str, max_age_hours: float = MAX_AGE_HOURS) -> str:
    """拼进 prompt 的一段：她自己刷到的东西，说不说随她。"""
    items = [x for x in (_load(mem, chat_id).get("items") or []) if _fresh(x, max_age_hours)]
    if not items:
        return ""
    items.sort(key=lambda x: (x.get("kind") == "hot", float(x.get("ts") or 0)), reverse=True)
    lines = ["【你自己刷到的东西（没人让你查，闲着刷的）】"]
    for x in items[:2]:
        head = "网上正火的" if x.get("kind") == "hot" else "你搜过的"
        line = f"- {head}「{x.get('q')}」：{x.get('title')}"
        if x.get("digest"):
            line += f"（{x['digest']}）"
        lines.append(line)
    lines.append(
        "要说就挑一条顺口提一句，或者拿来开个玩笑；不想说就当没看见。"
        "别提「搜索」「网页」「资料」，就像你刷到的。"
    )
    return "\n".join(lines)


def share_due(mem, chat_id: str) -> dict | None:
    """主动开聊用：有没有新鲜、还没给他看过的东西。"""
    items = [x for x in (_load(mem, chat_id).get("items") or []) if _fresh(x, SHARE_MAX_HOURS)]
    items = [x for x in items if not x.get("shared")]
    if not items:
        return None
    items.sort(key=lambda x: (x.get("kind") == "hot", float(x.get("ts") or 0)), reverse=True)
    return items[0]


def mark_shared(mem, chat_id: str, item: dict) -> None:
    d = _load(mem, chat_id)
    for x in d.get("items") or []:
        if x.get("title") == item.get("title"):
            x["shared"] = True
            x["shared_ts"] = time.time()
    _save(mem, chat_id, d)
