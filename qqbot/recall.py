"""旧事回忆检索：中文二元切分 + BM25，纯本地、零依赖、零成本。

为什么不用向量：中转站没有 embedding 接口，本地装模型又被网络卡死。
BM25 在“闲聊找回旧事”这个场景上比关键词 LIKE 强得多，因为它按相关性排序、
自动压低高频词（“今天”“什么”），也支持部分匹配。
"""

from __future__ import annotations

import math
import re
from collections import Counter

K1 = 1.5
B = 0.75

STOP = {
    "今天", "明天", "昨天", "现在", "什么", "怎么", "可以", "我们", "你们", "他们",
    "这个", "那个", "就是", "不是", "没有", "知道", "觉得", "时候", "还是", "但是",
    "因为", "所以", "如果", "然后", "真的", "好像", "一点", "有点", "感觉", "东西",
    "一个", "一下", "帮我", "给我", "是不", "而且", "其实", "可能", "应该", "这样",
}


def tokens(text: str) -> list[str]:
    """中文按二元切，英文/数字按词切，去掉高频虚词。"""
    text = (text or "").lower()
    out: list[str] = []
    for seg in re.findall(r"[\u4e00-\u9fa5]+", text):
        if len(seg) == 1:
            out.append(seg)
            continue
        out.extend(seg[i : i + 2] for i in range(len(seg) - 1))
    out.extend(re.findall(r"[a-z0-9]{2,}", text))
    return [t for t in out if t not in STOP]


class Index:
    """一次查询建一次索引——私聊量级（几千条）足够快，省去维护复杂度。"""

    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs
        self.tfs: list[Counter] = []
        self.lengths: list[int] = []
        df: Counter = Counter()
        for d in docs:
            tf = Counter(tokens(d["content"]))
            self.tfs.append(tf)
            self.lengths.append(sum(tf.values()) or 1)
            for term in tf:
                df[term] += 1
        self.n = len(docs)
        self.avgdl = (sum(self.lengths) / self.n) if self.n else 1.0
        self.idf = {t: math.log(1 + (self.n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def search(self, query: str, limit: int = 6, min_score: float = 1.2) -> list[dict]:
        q = tokens(query)
        if not q or not self.docs:
            return []
        scores: list[tuple[float, int]] = []
        for i, tf in enumerate(self.tfs):
            s = 0.0
            for term in q:
                if term not in tf:
                    continue
                idf = self.idf.get(term, 0.0)
                f = tf[term]
                denom = f + K1 * (1 - B + B * self.lengths[i] / self.avgdl)
                s += idf * f * (K1 + 1) / denom
            if s >= min_score:
                scores.append((s, i))
        scores.sort(key=lambda x: -x[0])
        out = []
        for s, i in scores[:limit]:
            d = dict(self.docs[i])
            d["score"] = round(s, 2)
            out.append(d)
        return out


def search_memory(mem, chat_id: str, query: str, skip_recent: int = 100, limit: int = 6) -> list[dict]:
    """从记忆库里找跟这句相关的旧对话（跳过最近 skip_recent 条）。"""
    try:
        docs = mem.all_messages(chat_id, limit=3000)
    except Exception:
        return []
    if not docs:
        return []
    docs.sort(key=lambda d: d["id"])
    if skip_recent > 0:
        docs = docs[:-skip_recent] if len(docs) > skip_recent else []
    if not docs:
        return []
    return Index(docs).search(query, limit=limit)
