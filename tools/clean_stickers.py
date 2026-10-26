"""表情包清理：丢掉太小/糊/重复的图，只留真能用的。

判定：最短边 < 180px 或体积 < 8KB 或 长宽比 > 3 的，删；内容 MD5 相同的，只留一张。
用法： .venv\\Scripts\\python.exe tools\\clean_stickers.py [--min 180] [--dry]
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "stickers"
EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=180, help="最短边下限（像素）")
    ap.add_argument("--min-bytes", type=int, default=8000)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    seen: dict[str, Path] = {}
    kept = dropped = 0
    reasons = {"small": 0, "tiny_bytes": 0, "ratio": 0, "dup": 0, "broken": 0}

    for p in sorted(OUT.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in EXTS:
            continue
        size = p.stat().st_size
        if size < args.min_bytes:
            reasons["tiny_bytes"] += 1
            dropped += 1
            if not args.dry:
                p.unlink()
            continue
        try:
            with Image.open(p) as im:
                w, h = im.size
        except Exception:
            reasons["broken"] += 1
            dropped += 1
            if not args.dry:
                p.unlink()
            continue
        if min(w, h) < args.min:
            reasons["small"] += 1
            dropped += 1
            if not args.dry:
                p.unlink()
            continue
        if max(w, h) / max(1, min(w, h)) > 3:
            reasons["ratio"] += 1
            dropped += 1
            if not args.dry:
                p.unlink()
            continue
        digest = hashlib.md5(p.read_bytes()).hexdigest()
        if digest in seen:
            reasons["dup"] += 1
            dropped += 1
            if not args.dry:
                p.unlink()
            continue
        seen[digest] = p
        kept += 1

    counts: dict[str, int] = {}
    for p in OUT.rglob("*"):
        if p.is_file() and p.suffix.lower() in EXTS:
            counts[p.parent.name] = counts.get(p.parent.name, 0) + 1
    print(f"保留 {kept} 张，清理 {dropped} 张 {reasons}")
    print("剩余分布：", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
