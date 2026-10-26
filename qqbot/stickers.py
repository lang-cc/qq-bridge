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
