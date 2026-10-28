"""看图：把截图/图片交给中转站的视觉模型，换一段文字描述。

用的是 OpenAI 兼容的 image_url（base64 内联），不额外依赖。
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

log = logging.getLogger("qqbot.vision")

DEFAULT_MODEL = "vision-auto"


async def describe(
    images: list[str],
    question: str = "这几张图里是什么内容？用两三句说清楚画面、人物和发生的事，不要评价。",
    base_url: str = "",
    api_key: str = "",
    model: str = DEFAULT_MODEL,
    max_images: int = 3,
) -> str:
    """返回模型对图片的描述；失败返回空串。"""
    import aiohttp

    picked = [p for p in images if str(p).startswith("http") or Path(p).exists()][:max_images]
    if not picked:
        return ""
    if not base_url or not api_key:
        return ""

    content: list[dict] = [{"type": "text", "text": question}]
    for p in picked:
        if str(p).startswith("http"):       # QQ 图片直接给链接，省一次下载
            content.append({"type": "image_url", "image_url": {"url": p}})
            continue
        try:
            b64 = base64.b64encode(Path(p).read_bytes()).decode()
        except Exception:
            continue
        suffix = Path(p).suffix.lower().lstrip(".") or "jpeg"
        mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})

    url = base_url.rstrip("/") + "/chat/completions"
    body = {"model": model, "messages": [{"role": "user", "content": content}], "temperature": 0.4}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=body, headers=headers, timeout=120) as r:
                data = await r.json(content_type=None)
        out = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        if out:
            log.info("看图完成（%d 张）：%s", len(picked), out[:60])
        return out
    except Exception as exc:
        log.warning("看图失败：%r", exc)
        return ""
