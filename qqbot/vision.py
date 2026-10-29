"""看图：把截图/图片交给中转站的视觉模型，换一段文字描述。

实测（这个中转站）：`vision-auto` 系列只认远程 URL，喂 base64 直接
400「图片输入格式/解析错误」；而且它自己回源拉 QQ 的图经常超时/502。
所以这里统一做成：**能下载就下载，自己转 base64 内联**，再交给认 base64 的
多模态模型（gpt-6.1-sol / kimi-k3.1-pro 实测可用）。下载失败才退回传链接。
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

log = logging.getLogger("qqbot.vision")

# 认 base64 内联、实测能出话的模型；不写死一个，按顺序试
DEFAULT_MODEL = "gpt-6.1-sol"
FALLBACK_MODELS = ("gpt-6.1-sol", "kimi-k3.1-pro")

MAX_BYTES = 8 * 1024 * 1024


def _mime_of(name: str) -> str:
    suffix = Path(name).suffix.lower().lstrip(".") or "jpeg"
    if suffix in ("jpg", "jpeg"):
        return "image/jpeg"
    if suffix in ("png", "gif", "webp", "bmp"):
        return f"image/{suffix}"
    return "image/jpeg"


def _sniff_mime(raw: bytes, name: str = "") -> str:
    """按文件头判断真实类型：QQ 的图链接常带 ?参数、后缀也不一定靠得住，
    标错 MIME 会让模型把透明区域看成一块灰。"""
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if raw[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return _mime_of(name)


async def _as_data_url(session, p: str) -> str:
    """http 图片先自己下载再内联；下载不了就原样传链接，交给上游试试。"""
    if not str(p).startswith("http"):
        try:
            raw = Path(p).read_bytes()
        except Exception:
            return ""
        return f"data:{_sniff_mime(raw, p)};base64,{base64.b64encode(raw).decode()}"
    try:
        async with session.get(str(p), timeout=25) as r:
            if r.status != 200:
                log.debug("下载图片 %s 失败：HTTP %s", str(p)[:60], r.status)
                return str(p)
            raw = await r.content.read(MAX_BYTES)
    except Exception as exc:
        log.debug("下载图片 %s 失败：%r，改用链接直传", str(p)[:60], exc)
        return str(p)
    if not raw:
        return str(p)
    return f"data:{_sniff_mime(raw, str(p).split('?')[0])};base64,{base64.b64encode(raw).decode()}"


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

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    models: list[str] = []
    for m in [model, *FALLBACK_MODELS]:
        if m and m not in models:
            models.append(m)

    async with aiohttp.ClientSession() as s:
        parts: list[dict] = [{"type": "text", "text": question}]
        for p in picked:
            data_url = await _as_data_url(s, p)
            if data_url:
                parts.append({"type": "image_url", "image_url": {"url": data_url}})
        if len(parts) < 2:
            log.warning("看图失败：一张图都没取到（%r）", images)
            return ""

        for m in models:
            body = {"model": m, "messages": [{"role": "user", "content": parts}], "temperature": 0.4}
            # 有没下载下来的图（还挂着远程链接）就别等太久，上游回源拉 QQ 的图经常卡死
            loose = any(str(x.get("image_url", {}).get("url", "")).startswith("http") for x in parts)
            try:
                async with s.post(url, json=body, headers=headers, timeout=35 if loose else 120) as r:
                    data = await r.json(content_type=None)
            except Exception as exc:
                log.warning("看图失败（%s）：%r", m, exc)
                continue
            err = (data.get("error") or {}).get("message") if isinstance(data, dict) else ""
            out = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
            if out:
                log.info("看图完成（%d 张，%s）：%s", len(picked), m, out[:60])
                return out
            log.warning("看图没出内容（%s）：%s", m, (err or str(data))[:120])
    return ""
