"""批量下载开源表情包（zhaoolee/ChineseBQB）到 stickers/，按主题归到心情目录。

只调用一次 GitHub tree 接口拿全量文件清单（省 API 额度），然后走 gh-proxy 并发下载。
用法：
  .venv\\Scripts\\python.exe tools\\fetch_stickers.py --count 250
"""

from __future__ import annotations

import argparse
import json
import random
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "stickers"
REPO = "zhaoolee/ChineseBQB"
PROXIES = ["https://gh-proxy.com/", "https://ghfast.top/"]
EXTS = {".gif", ".jpg", ".jpeg", ".png"}
MAX_BYTES = 900_000

BUCKET_HINTS = {
    "开心": ["笑", "滑稽", "开心", "高兴", "得意", "Pikachu", "皮卡丘", "Hamster", "仓鼠", "Duck", "Funny"],
    "生气": ["怒", "生气", "暴躁", "怼", "骂", "Tiger", "胖虎", "凶"],
    "难过": ["哭", "难过", "委屈", "伤心", "泪", "丧"],
    "困": ["困", "睡", "晚安", "打哈欠"],
}


def tree() -> list[dict]:
    url = f"https://api.github.com/repos/{REPO}/git/trees/master?recursive=1"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "qq-bridge"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read().decode())
    return data.get("tree") or []


def bucket_of(path: str) -> str:
    for bucket, keys in BUCKET_HINTS.items():
        if any(k in path for k in keys):
            return bucket
    return "日常"


def download(path: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 200:
        return True
    quoted = "/".join(urllib.parse.quote(p) for p in path.split("/"))
    src = f"https://raw.githubusercontent.com/{REPO}/master/{quoted}"
    for proxy in PROXIES:
        try:
            req = urllib.request.Request(proxy + src, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read(MAX_BYTES + 1)
            if len(data) < 300:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return True
        except Exception:
            continue
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=250)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--folders", type=str, default="", help="只下这些主题目录（逗号分隔前缀）")
    ap.add_argument("--per", type=int, default=0, help="每个主题最多几张（0=不限）")
    args = ap.parse_args()

    print("拉取仓库文件清单…", flush=True)
    items = tree()
    blobs = [
        it
        for it in items
        if it.get("type") == "blob"
        and Path(it["path"]).suffix.lower() in EXTS
        and 0 < it.get("size", 0) <= MAX_BYTES
    ]
    if args.folders:
        prefixes = [f.strip() for f in args.folders.split(",") if f.strip()]
        blobs = [it for it in blobs if any(it["path"].startswith(p) for p in prefixes)]
        print(f"按主题过滤后 {len(blobs)} 张", flush=True)
    print(f"可用图片 {len(blobs)} 个", flush=True)
    random.seed(7)
    random.shuffle(blobs)

    if args.per > 0:
        per_folder: dict[str, int] = {}
        picked = []
        for it in blobs:
            folder = it["path"].split("/")[0]
            if per_folder.get(folder, 0) >= args.per:
                continue
            per_folder[folder] = per_folder.get(folder, 0) + 1
            picked.append(it)
        print("每主题上限", args.per, "，选中", len(picked), "张", flush=True)
    else:
        picked = blobs[: args.count]

    jobs = []
    for it in picked:
        path = it["path"]
        safe = "".join(c for c in Path(path).stem if c.isalnum() or c in "-_")[:28] or "bqb"
        bucket = bucket_of(path)
        dest = OUT / bucket / f"{safe}{Path(path).suffix.lower()}"
        if dest.exists():
            continue
        jobs.append((path, dest))

    print(f"待下载 {len(jobs)} 张，并发 {args.workers}", flush=True)
    ok = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(download, p, d): d for p, d in jobs}
        for i, fut in enumerate(as_completed(futs), 1):
            dest = futs[fut]
            try:
                if fut.result():
                    ok += 1
            except Exception:
                pass
            if i % 25 == 0:
                print(f"  进度 {i}/{len(jobs)}，成功 {ok}", flush=True)

    counts: dict[str, int] = {}
    for p in OUT.rglob("*"):
        if p.is_file() and p.suffix.lower() in EXTS:
            counts[p.parent.name] = counts.get(p.parent.name, 0) + 1
    print(f"\n本次下载成功 {ok} 张")
    print("图库现状：", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
