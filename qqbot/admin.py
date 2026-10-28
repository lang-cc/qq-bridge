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


def _splice_list(text: str, kind: str, values: list[str]) -> str:
    """把 config.yaml 里 autoreply.whitelist.<kind> 的列表原地换掉，别的字节一个都不动。

    整份 safe_dump 会把注释全抹掉，用户手写的排版也没了 —— 加个白名单不该有这种代价。
    """
    import re

    lines = text.splitlines(keepends=True)

    # 1 找 whitelist: 那一行
    wi = wind = None
    for i, ln in enumerate(lines):
        m = re.match(r"^([ \t]*)whitelist[ \t]*:[ \t]*(?:#.*)?$", ln)
        if m:
            wi, wind = i, len(m.group(1))
            break
    if wi is None:
        raise ValueError("config.yaml 里没找到 whitelist:")

    # 2 在它的块里找 users: / groups:
    ki = kind_ind = None
    inline = ""
    for j in range(wi + 1, len(lines)):
        raw = lines[j]
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        ind = len(raw) - len(raw.lstrip())
        if ind <= wind:
            break                      # 出了 whitelist 块
        m = re.match(r"^[ \t]*%s[ \t]*:[ \t]*(.*)$" % kind, raw)
        if m:
            ki, kind_ind, inline = j, ind, m.group(1).strip()
            break
    if ki is None:
        raise ValueError("config.yaml 里没找到 whitelist.%s:" % kind)

    # 3 算出这个值占了几行（单行 [a, b] 形式 / 多行 - a 形式）
    end = ki + 1
    if not inline or inline.startswith("#"):
        while end < len(lines):
            s = lines[end].strip()
            if not s:
                k = end + 1
                while k < len(lines) and not lines[k].strip():
                    k += 1
                if k < len(lines) and lines[k].strip().startswith("- "):
                    end = k
                    continue
                break
            ind = len(lines[end]) - len(lines[end].lstrip())
            if s.startswith("- ") and ind >= kind_ind:
                end += 1
                continue
            break

    pad = " " * kind_ind
    if values:
        block = ["%s%s:\n" % (pad, kind)] + ["%s- '%s'\n" % (pad, v) for v in values]
    else:
        block = ["%s%s: []\n" % (pad, kind)]
    return "".join(lines[:ki] + block + lines[end:])


def edit_whitelist(kind: str, values: list[str], path: Path = CONFIG_PATH) -> list[str]:
    """改白名单里的 users / groups，返回落盘后的列表。

    先做文本替换（保留注释）；替换完立刻回读校验，万一对不上就退回整份重写，保证配置不会写坏。
    """
    import yaml

    if kind not in ("users", "groups"):
        raise ValueError("kind 只能是 users 或 groups")
    clean: list[str] = []
    for v in values:
        v = str(v).strip().strip("'\"")
        if v and v not in clean:
            clean.append(v)

    text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text) or {}
    ar = raw.get("autoreply")
    if not isinstance(ar, dict):
        raise ValueError("config.yaml 里没有 autoreply 段")
    wl = ar.get("whitelist")
    if not isinstance(wl, dict):
        wl = ar["whitelist"] = {}

    try:
        new_text = _splice_list(text, kind, clean)
        probe = yaml.safe_load(new_text) or {}
        got = ((probe.get("autoreply") or {}).get("whitelist") or {}).get(kind) or []
        if [str(x) for x in got] != clean:
            raise ValueError("回读校验不一致：%r" % (got,))
    except Exception as exc:
        log.warning("白名单文本替换失败（%r），退回整份重写 config.yaml", exc)
        wl[kind] = clean
        save_config(raw, path)
        return clean

    shutil.copyfile(path, str(path) + ".bak")
    path.write_text(new_text, encoding="utf-8")
    log.info("白名单 %s 已更新：%d 条", kind, len(clean))
    return clean


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
    _t = llm.get("temperature")
    try:
        _t = float(_t if _t is not None else 0.9)
    except (TypeError, ValueError):
        _t = 0.9
    if 2.0 < _t <= 100.0:  # 配置台把 70（=0.7）写成百分数时救一下
        _t = _t / 100.0
    body = {
        "model": llm.get("model") or "",
        "messages": [{"role": "system", "content": persona.strip()}, {"role": "user", "content": text}],
        "temperature": max(0.0, min(2.0, _t)),
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
    except Exception as exc:
        return {"ok": False, "error": repr(exc)}

    rows = [m for m in (data.get("data") or []) if isinstance(m, dict) and m.get("id")]
    models = sorted({m["id"] for m in rows})
    detail, seen = [], set()
    for m in sorted(rows, key=lambda x: str(x["id"])):
        if m["id"] in seen:
            continue
        seen.add(m["id"])
        ctx = (m.get("context_window") or m.get("context_length")
               or m.get("max_context_tokens") or m.get("max_input_tokens") or 0)
        try:
            ctx = int(ctx or 0)
        except Exception:
            ctx = 0
        detail.append({
            "id": m["id"],
            "name": str(m.get("name") or ""),
            "owner": str(m.get("owned_by") or ""),
            "context": ctx,
        })
    # 一起返回 count / endpoint：页面上能看出这些就是接口自己给的全部，不是被截断
    return {"ok": True, "models": models, "detail": detail,
            "count": len(models), "endpoint": f"{base}/models"}
