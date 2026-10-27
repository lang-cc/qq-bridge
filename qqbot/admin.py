"""配置图形界面：改人设 / 模型 / 开关，保存即生效（不用重启）。

保存会重写 config.yaml（注释会丢），每次保存前自动备份成 config.yaml.bak。
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

log = logging.getLogger("qqbot.admin")

CONFIG_PATH = Path("config.yaml")

from .admin_page import PAGE  # noqa: F401  页面单独一个文件，方便改样式

def save_config(raw: dict, path: Path = CONFIG_PATH) -> None:
    import yaml

    if path.exists():
        shutil.copyfile(path, str(path) + ".bak")
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)


async def test_llm(autoreply: dict, text: str) -> dict:
    import time

    import aiohttp

    llm = (autoreply or {}).get("llm") or {}
    if not llm.get("enabled", True):
        return {"ok": False, "error": "AI 未启用"}
    base = str(llm.get("base_url") or "").rstrip("/")
    if not base:
        return {"ok": False, "error": "base_url 为空"}
    persona = (llm.get("persona") or "") + "\n" + (llm.get("system_prompt") or "")
    body = {
        "model": llm.get("model") or "",
        "messages": [{"role": "system", "content": persona.strip()}, {"role": "user", "content": text}],
        "temperature": float(llm.get("temperature") or 0.9),
    }
    headers = {"Content-Type": "application/json"}
    if llm.get("api_key"):
        headers["Authorization"] = f"Bearer {llm['api_key']}"
    t0 = time.monotonic()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{base}/chat/completions", json=body, headers=headers, timeout=90) as r:
                data = await r.json(content_type=None)
        msg = ((data.get("choices") or [{}])[0].get("message") or {})
        return {
            "ok": True,
            "reply": (msg.get("content") or "").strip(),
            "reasoning": (msg.get("reasoning_content") or ""),
            "model": llm.get("model"),
            "ms": int((time.monotonic() - t0) * 1000),
        }
    except Exception as exc:
        return {"ok": False, "error": repr(exc)}


async def list_models(autoreply: dict) -> dict:
    import aiohttp

    llm = (autoreply or {}).get("llm") or {}
    base = str(llm.get("base_url") or "").rstrip("/")
    if not base:
        return {"ok": False, "error": "base_url 为空"}
    headers = {}
    if llm.get("api_key"):
        headers["Authorization"] = f"Bearer {llm['api_key']}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{base}/models", headers=headers, timeout=30) as r:
                data = await r.json(content_type=None)
        models = sorted({m.get("id") for m in (data.get("data") or []) if m.get("id")})
        return {"ok": True, "models": models}
    except Exception as exc:
        return {"ok": False, "error": repr(exc)}
