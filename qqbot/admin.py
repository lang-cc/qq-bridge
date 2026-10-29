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


def _norm_base(base: str) -> str:
    b = str(base or "").strip().rstrip("/")
    for tail in ("/chat/completions", "/completions", "/models"):
        if b.endswith(tail):
            b = b[: -len(tail)].rstrip("/")
    return b


def _suggest(ids: list[str], model: str) -> list[str]:
    """模型名打错时给出相近的名字，别让人干瞪眼。"""
    m = str(model or "").lower()
    pref = m.split("-")[0] if m else ""
    cands = [i for i in ids if pref and pref in i.lower()]
    return (cands or ids)[:4]


def _err_hint(status: int, body: str, model: str) -> tuple[str, str]:
    """把 HTTP 错误翻译成人话：到底是密钥、模型名、还是额度的问题。"""
    low = (body or "").lower()
    if status in (401, 403):
        return "密钥无效或没权限", "去控制台确认这串 key 没写错、没过期、没被限制 IP"
    if status == 404:
        return "接口地址或模型名不对（404）", (
            "多半是 base_url 少了 /v1（OpenAI 兼容要写 https://xxx/v1），"
            f"或者模型名 {model or '(空)'} 这个接口没有"
        )
    if status == 429:
        return "被限流 / 额度用完了（429）", "等一会儿再试，或去充值/换 key"
    if status == 402:
        return "余额不足（402）", "去供应商后台充值"
    if "insufficient" in low or "quota" in low or "balance" in low:
        return "额度不足", "去供应商后台看余额/额度"
    if "model" in low and ("not exist" in low or "not found" in low or "invalid" in low):
        return f"模型名 {model or '(空)'} 不存在", "点「拉取可用模型」从列表里挑，别手打"
    if status == 400:
        return "请求被拒（400）", body[:200]
    if status >= 500:
        return f"对方服务端出错（{status}）", "过一会儿再试；持续如此说明供应商挂了"
    return f"调用失败（{status}）", body[:200]


async def test_llm(autoreply: dict, text: str) -> dict:
    """保存前验一遍：密钥到底通不通、模型名对不对、能不能真生成一句话。

    步骤故意分两层，错在哪一层一眼能看出来：
      1) GET  {base}/models        → 只验密钥（不花 token）
      2) POST {base}/chat/completions → 验模型名 + 真能出字（花几个 token）
    """
    import time

    import aiohttp

    llm = (autoreply or {}).get("llm") or {}
    base = _norm_base(llm.get("base_url"))
    key = str(llm.get("api_key") or "").strip()
    model = str(llm.get("model") or "").strip()
    out: dict = {
        "ok": False, "base_url": base, "model": model,
        "key_ok": None, "key_msg": "", "models": 0, "models_hint": "",
        "model_found": None, "reply": "", "ms": 0, "error": "", "hint": "",
    }
    if not llm.get("enabled", True):
        out.update(error="AI 未启用", hint="模型页看不到开关的话，改 config.yaml 的 autoreply.llm.enabled")
        return out
    if not base:
        out.update(error="base_url 为空", hint="例如 https://api.deepseek.com/v1")
        return out
    if not key:
        out.update(error="api_key 为空", hint="把供应商给的 key 粘进「API Key」")
        return out

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    # ---- 1) 只验密钥 ----
    t0 = time.monotonic()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{base}/models", headers=headers, timeout=20) as r:
                status = r.status
                raw = await r.text()
    except Exception as exc:
        out.update(error="连不上接口", hint=f"{exc!r}；检查 base_url、本机能不能上外网、要不要代理")
        return out

    ids: list[str] = []
    if status == 200:
        try:
            import json as _json

            data = _json.loads(raw)
            ids = [str(m.get("id")) for m in (data.get("data") or []) if isinstance(m, dict) and m.get("id")]
        except Exception:
            ids = []
        out["key_ok"] = True
        out["models"] = len(ids)
        out["key_msg"] = f"密钥有效（接口报了 {len(ids)} 个模型）"
        if model and ids:
            exact = model in ids
            loose = [i for i in ids if i.lower() == model.lower() or i.startswith(model)]
            out["model_found"] = bool(exact or loose)
            if not exact and loose:
                out["hint"] = f"模型名不完全一致，接口里有：{', '.join(loose[:3])}"
    elif status in (404, 405):
        out["key_ok"] = None
        out["key_msg"] = "这个接口没有 /models，跳过密钥单验，直接试生成"
    else:
        msg, hint = _err_hint(status, raw, model)
        out.update(key_ok=False, key_msg=msg, error=msg, hint=hint)
        return out

    # ---- 2) 真生成一句话（max_tokens 压到很小，几乎不花钱）----
    persona = (llm.get("persona") or "").strip()
    body = {
        "model": model,
        "messages": ([{"role": "system", "content": persona[:200]}] if persona else [])
        + [{"role": "user", "content": text or "只回两个字：在的"}],
        "max_tokens": 64,
        "stream": False,
    }
    try:
        _t = float(llm.get("temperature") if llm.get("temperature") is not None else 0.9)
        if 2.0 < _t <= 100.0:
            _t = _t / 100.0
        body["temperature"] = max(0.0, min(2.0, _t))
    except (TypeError, ValueError):
        pass

    async def _call(payload: dict) -> tuple[int, str]:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{base}/chat/completions", json=payload, headers=headers, timeout=90) as r:
                return r.status, await r.text()

    try:
        status, raw = await _call(body)
        if status == 200:
            try:
                import json as _json

                _probe = _json.loads(raw)
                _empty = not (((_probe.get("choices") or [{}])[0].get("message") or {})
                              .get("content") or "").strip()
            except Exception:
                _empty = False
            if _empty:
                # 推理型模型会把 budget 先花在 reasoning 上，32/64 个 token 出不来正文 —— 放大再试一次
                body2 = dict(body, max_tokens=256)
                status, raw = await _call(body2)
    except Exception as exc:
        out.update(error="生成请求发不出去", hint=repr(exc))
        return out

    if status != 200:
        msg, hint = _err_hint(status, raw, model)
        low = raw.lower()
        # 网关对「模型名不存在」经常回 404 而不是 400，单看状态码会误判成地址写错
        if "model_not_found" in low or "not supported" in low or "no such model" in low:
            cands = _suggest(ids, model)
            msg = f"模型名 {model or '(空)'} 这个接口没有"
            hint = ("接口里有相近的：" + "、".join(cands)) if cands else "点「拉取可用模型」从列表里挑一个"
        out.update(error=msg, hint=hint)
        return out

    try:
        import json as _json

        data = _json.loads(raw)
        msg_obj = ((data.get("choices") or [{}])[0].get("message") or {})
        reply = (msg_obj.get("content") or "").strip()
        usage = data.get("usage") or {}
    except Exception:
        out.update(error="接口返回的不是标准 OpenAI 格式", hint=raw[:200])
        return out

    out.update(
        ok=True,
        reply=reply,
        ms=int((time.monotonic() - t0) * 1000),
        model=data.get("model") or model,
        tokens=f"{usage.get('prompt_tokens', '?')}+{usage.get('completion_tokens', '?')}",
    )
    if not reply:
        out.update(error="能连上，但模型返回空内容",
                   hint="可能是推理型模型把内容放在 reasoning 里，或 max_tokens 太小被截断")
    return out


async def test_tts(autoreply: dict) -> dict:
    """语音合成能不能通：拿一句短话真合成一条 silk，返回耗时和文件大小。"""
    import os
    import time

    from . import tts as _tts

    cfg = (autoreply or {}).get("tts") or {}
    provider = str(cfg.get("provider") or "").strip().lower()
    out: dict = {
        "ok": False, "provider": provider, "model": str(cfg.get("model") or ""),
        "voice": str(cfg.get("voice") or ""), "ms": 0, "file": "", "size": 0,
        "error": "", "hint": "",
    }
    if not provider:
        out.update(error="没配语音（这项留空就是只发文字）",
                   hint="想让她发语音：在上面选个提供方，填模型名 / 音色 ID，阿里云还要填 API Key")
        return out
    if not cfg.get("enabled", True):
        out.update(error="语音合成关着", hint="config.yaml 的 autoreply.tts.enabled 改成 true")
        return out
    if provider in ("aliyun", "qwen", "bailian") and not str(cfg.get("api_key") or "").strip():
        out.update(error="阿里云要 API Key", hint="填 DashScope 的 sk-…（百炼控制台 → API-KEY）")
        return out

    t0 = time.monotonic()
    try:
        path = await _tts.speak("测试一下，一二三", cfg=cfg)
    except Exception as exc:
        out.update(error="合成过程抛异常", hint=repr(exc)[:200])
        return out
    if not path:
        out.update(error="合成失败（阿里云/edge/百度/本机 全都试过，没出一条）",
                   hint="看 Key、模型名、音色 ID 对不对；日志 logs/qqbot.log 里有每一层的报错")
        return out

    size = os.path.getsize(path) if os.path.exists(path) else 0
    # 以前只回文件名：调用方拿着 voice.silk 去发，协议端在自己的工作目录里找不到，报 ENOENT。
    # 这里把绝对路径一起给出来，谁要用这条语音都能直接用。
    out.update(ok=True, ms=int((time.monotonic() - t0) * 1000),
               file=os.path.basename(path), path=os.path.abspath(path), size=size)
    if size < 2000:
        out.update(error="合成出来的音频偏小，可能不太正常", hint=f"{size} 字节，听一下文件对不对")
    return out


async def list_models(autoreply: dict) -> dict:
    import aiohttp

    llm = (autoreply or {}).get("llm") or {}
    base = _norm_base(llm.get("base_url"))
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
