"""偷表情包：把别人发来的图片/表情存进本地图库，之后自己也能发。

只存图片段（OneBot 的 image segment），单张上限 900KB，按内容哈希去重。
"""

from __future__ import annotations

import base64
import hashlib
import logging
from pathlib import Path

log = logging.getLogger("qqbot.steal")

EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_BYTES = 900_000


def _segments(event) -> list[dict]:
    raw = getattr(event, "raw", None) or {}
    msg = raw.get("message")
    return msg if isinstance(msg, list) else []


def image_urls(event) -> list[str]:
    urls = []
    for seg in _segments(event):
        if seg.get("type") != "image":
            continue
        data = seg.get("data") or {}
        url = data.get("url") or data.get("file") or ""
        if url:
            urls.append(str(url))
    return urls


async def steal(event, root: str | Path = "stickers", bucket: str = "偷来的") -> Path | None:
    """把这条消息里的第一张图存进图库，返回路径。"""
    import aiohttp

    urls = image_urls(event)
    if not urls:
        return None

    dest_dir = Path(root) / bucket
    dest_dir.mkdir(parents=True, exist_ok=True)

    for url in urls[:3]:
        try:
            if url.startswith("base64://"):
                data = base64.b64decode(url[len("base64://") :])
            elif url.startswith(("http://", "https://")):
                async with aiohttp.ClientSession() as s:
                    async with s.get(url, timeout=25) as r:
                        if r.status != 200:
                            continue
                        data = await r.content.read(MAX_BYTES + 1)
            else:
                p = Path(url.replace("file:///", ""))
                if not p.exists():
                    continue
                data = p.read_bytes()[: MAX_BYTES + 1]
            if len(data) < 500 or len(data) > MAX_BYTES:
                continue

            head = data[:4]
            ext = ".gif" if head[:3] == b"GIF" else ".png" if head[:4] == b"\x89PNG" else ".jpg"
            digest = hashlib.md5(data).hexdigest()[:16]
            dest = dest_dir / f"{digest}{ext}"
            if dest.exists():
                return dest
            dest.write_bytes(data)
            log.info("偷到表情包 %s（%d KB）", dest.name, len(data) // 1024)
            return dest
        except Exception as exc:
            log.debug("偷图失败 %s：%r", url[:60], exc)
    return None
