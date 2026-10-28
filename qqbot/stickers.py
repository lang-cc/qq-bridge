"""表情包库：按心情挑图发送，没有图就退回 QQ 原生表情。"""

from __future__ import annotations

import logging
import random
from pathlib import Path

log = logging.getLogger("qqbot.stickers")

EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

# 心情标签 -> 可用的目录别名
MOOD_ALIASES = {
    "开心": ["开心", "高兴", "happy", "笑"],
    "还行": ["日常", "默认", "default", "普通"],
    "低落": ["难过", "低落", "sad", "委屈"],
    "困": ["困", "sleep", "晚安"],
    "生气": ["生气", "无语", "angry"],
}

# 文字里出现这些词，就优先挑对应图库 —— 不然「想吃」配「我没事你忙你的」会很怪
TEXT_TAGS = {
    "开心": ("哈哈", "笑死", "乐", "开心", "高兴", "好耶", "想吃", "馋", "香", "太好了", "厉害",
             "喜欢", "可爱", "牛", "棒", "行啊", "可以啊", "真的假的"),
    "困": ("困", "睡", "睡觉", "晚安", "累", "困死", "眼睛", "眯", "午觉"),
    "生气": ("烦", "气", "讨厌", "凶", "骂", "闭嘴", "滚", "不理", "别烦", "哼"),
    "难过": ("委屈", "难过", "呜", "哭", "疼", "惨", "算了", "没事", "心里", "难受", "唉"),
    "日常": ("嗯", "好", "行", "哦", "啊", "在", "咋了", "没事", "等下", "马上", "来了", "知道"),
}

# QQ 原生表情 id（作为后备，不占流量）
QQ_FACES = [14, 1, 5, 13, 101, 178, 179, 182, 183, 212, 264, 265, 266, 307, 311, 312]


class Stickers:
    def __init__(self, root: str = "stickers") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, list[Path]] = {}

    def scan(self) -> dict[str, list[Path]]:
        lib: dict[str, list[Path]] = {}
        for p in self.root.rglob("*"):
            if p.is_file() and p.suffix.lower() in EXTS:
                lib.setdefault(p.parent.name or "默认", []).append(p)
        self._cache = lib
        return lib

    def count(self) -> int:
        return sum(len(v) for v in self.scan().values())

    def _bucket(self, lib: dict[str, list[Path]], tag: str, skip: tuple[str, ...] = ()) -> Path | None:
        for name in lib:
            if any(x in name for x in skip):
                continue
            if tag in name:
                return random.choice(lib[name])
        return None

    def pick_for(self, text: str, mood_label: str = "") -> Path | None:
        """先看这句话在说什么，再退到心情。都对不上才进「偷来的」兜底。"""
        lib = self._cache or self.scan()
        if not lib:
            return None
        t = text or ""
        hit_tag = None
        for tag, words in TEXT_TAGS.items():
            if any(w in t for w in words):
                if tag == "日常" and len(t.strip()) <= 10:
                    continue        # 「日常」180 多张什么都有，短句不值得配图
                hit_tag = tag
                hit = self._bucket(lib, tag)
                if hit is not None:
                    return hit
        # 没有情绪线索（或者只沾到「日常」这种万金油标签）就别配图：
        # 日常库 180 多张什么都有，抽到「吃饱了」配「我嘴笨」就是这么来的。
        # 只有句子够长（真说了点事）才允许按心情兜底。
        if hit_tag is None and len(t.strip()) < 12:
            return None
        # 文字没线索：按心情
        for bucket, aliases in MOOD_ALIASES.items():
            if bucket and bucket in (mood_label or ""):
                for alias in aliases:
                    hit = self._bucket(lib, alias)
                    if hit is not None:
                        return hit
        # 「日常」库 180 多张、什么都有，抽到「吃饱了」配「我嘴笨」就是这么来的：
        # 只在一半概率下用它兜底，另一半干脆不发
        if random.random() < 0.5:
            for alias in MOOD_ALIASES["还行"][:4]:
                hit = self._bucket(lib, alias)
                if hit is not None:
                    return hit
        hit = self._bucket(lib, "偷来的")
        return hit if (hit is not None and random.random() < 0.3) else None

    def pick(self, mood_label: str) -> Path | None:
        lib = self._cache or self.scan()
        if not lib:
            return None
        names = list(lib.keys())
        # 心情优先
        for bucket, aliases in MOOD_ALIASES.items():
            if bucket and bucket in (mood_label or ""):
                for alias in aliases:
                    for name in names:
                        if alias.lower() in name.lower():
                            return random.choice(lib[name])
        # 退到「日常/默认」，再退到全库
        for alias in MOOD_ALIASES["还行"][:4]:
            for name in names:
                if alias.lower() in name.lower():
                    return random.choice(lib[name])
        allp = [p for v in lib.values() for p in v]
        return random.choice(allp) if allp else None


def random_face() -> int:
    return random.choice(QQ_FACES)
