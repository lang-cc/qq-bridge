"""配置图形界面：改人设 / 模型 / 开关，保存即生效（不用重启）。

保存会重写 config.yaml（注释会丢），每次保存前自动备份成 config.yaml.bak。
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

log = logging.getLogger("qqbot.admin")

CONFIG_PATH = Path("config.yaml")

PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>qq-bridge 控制台</title>
<style>
  :root{--bg:#0f1117;--card:#181b24;--line:#262b38;--fg:#e6e9ef;--dim:#8b93a7;--acc:#4f7cff;--ok:#31c48d;--warn:#f0b429}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;padding:24px}
  .wrap{max-width:900px;margin:0 auto}
  h1{font-size:20px;margin:0 0 4px;display:flex;align-items:center;gap:10px}
  .badge{font-size:12px;padding:2px 8px;border-radius:20px;background:#1f2534;color:var(--dim);font-weight:400}
  .badge.on{background:rgba(49,196,141,.14);color:var(--ok)}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:16px}
  .card h2{font-size:14px;margin:0 0 14px;color:var(--dim);font-weight:600;letter-spacing:.5px}
  .row{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:12px}
  .field{flex:1;min-width:180px}
  label{display:block;font-size:12px;color:var(--dim);margin-bottom:5px}
  input[type=text],input[type=number],textarea,select{width:100%;padding:9px 11px;background:#11141c;border:1px solid var(--line);border-radius:9px;color:var(--fg);font:13px/1.5 inherit;outline:none}
  input:focus,textarea:focus,select:focus{border-color:var(--acc)}
  textarea{min-height:120px;resize:vertical;line-height:1.7}
  .switch{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--fg)}
  .switch input{width:16px;height:16px;accent-color:var(--acc)}
  button{padding:9px 18px;border:0;border-radius:9px;background:var(--acc);color:#fff;font-size:13px;font-weight:600;cursor:pointer}
  button.ghost{background:#1f2534;color:var(--fg)}
  button:active{transform:translateY(1px)}
  .bar{display:flex;gap:10px;align-items:center;position:sticky;bottom:0;background:linear-gradient(transparent,var(--bg) 30%);padding:14px 0}
  .hint{font-size:12px;color:var(--dim);margin-top:6px}
  pre{background:#0b0e14;border:1px solid var(--line);border-radius:9px;padding:12px;white-space:pre-wrap;font-size:13px;margin:0;min-height:20px}
  .toast{position:fixed;right:20px;bottom:20px;background:var(--ok);color:#06281c;padding:10px 16px;border-radius:10px;font-weight:600;opacity:0;transition:.25s}
  .toast.show{opacity:1}
</style>
</head>
<body>
<div class="wrap">
  <h1>qq-bridge 控制台 <span class="badge" id="status">加载中…</span></h1>
  <div class="hint" id="meta" style="margin-bottom:18px"></div>

  <div class="card">
    <h2>模型（像不像真人主要看这里）</h2>
    <div class="row">
      <div class="field" style="flex:2">
        <label>模型</label>
        <input type="text" id="model" list="models" placeholder="deepseek-v4-flash">
        <datalist id="models"></datalist>
      </div>
      <div class="field">
        <label>温度（越高越活，0.8–1.1）</label>
        <input type="number" id="temperature" step="0.05" min="0" max="2">
      </div>
      <div class="field">
        <label>记忆轮数</label>
        <input type="number" id="history" min="0" max="30">
      </div>
    </div>
    <div class="row">
      <div class="field" style="flex:2">
        <label>接口地址 base_url</label>
        <input type="text" id="base_url">
      </div>
      <div class="field" style="flex:2">
        <label>API Key</label>
        <input type="text" id="api_key">
      </div>
    </div>
    <div class="row">
      <div class="field">
        <label>人设 / 说话风格（最重要）</label>
        <textarea id="persona"></textarea>
      </div>
    </div>
    <div class="row" style="margin-bottom:0">
      <button class="ghost" onclick="loadModels()">拉取可用模型</button>
      <span class="hint" style="margin:8px 0 0">建议选「非推理型」模型，回复快、也更像人</span>
    </div>
  </div>

  <div class="card">
    <h2>行为</h2>
    <div class="row">
      <div class="field"><label class="switch"><input type="checkbox" id="enabled"> 启用自动回复</label></div>
      <div class="field"><label class="switch"><input type="checkbox" id="llm_enabled"> 启用 AI</label></div>
      <div class="field"><label class="switch"><input type="checkbox" id="typing_enabled"> 模拟打字</label></div>
      <div class="field"><label class="switch"><input type="checkbox" id="split_enabled"> 长回复分段</label></div>
    </div>
    <div class="row">
      <div class="field"><label class="switch"><input type="checkbox" id="reply_private"> 回私聊</label></div>
      <div class="field"><label class="switch"><input type="checkbox" id="reply_group"> 回群聊</label></div>
      <div class="field"><label class="switch"><input type="checkbox" id="group_at_only"> 群里只回 @</label></div>
      <div class="field"><label>群回复概率</label><input type="number" id="group_reply_probability" step="0.1" min="0" max="1"></div>
    </div>
    <div class="row">
      <div class="field"><label>冷却（秒）</label><input type="number" id="cooldown" step="0.5" min="0"></div>
      <div class="field"><label>每字延迟 ms</label><input type="number" id="per_char_ms" min="0"></div>
      <div class="field"><label>延迟上限 ms</label><input type="number" id="max_ms" min="0"></div>
      <div class="field"><label>最多分几条</label><input type="number" id="max_segments" min="1" max="6"></div>
    </div>
    <div class="row" style="margin-bottom:0">
      <div class="field"><label>兜底回复（AI 挂了时说）</label><input type="text" id="fallback"></div>
    </div>
  </div>

  <div class="card">
    <h2>试聊（用当前设置跑一遍，不发给 QQ）</h2>
    <div class="row">
      <div class="field" style="flex:3"><input type="text" id="testin" value="你是谁啊 怎么突然加我"></div>
      <button onclick="testChat()">发送测试</button>
    </div>
    <pre id="testout">（还没测）</pre>
  </div>

  <div class="bar">
    <button onclick="save()">保存配置</button>
    <span class="hint" id="saved"></span>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
let CFG = {};
const TOKEN = new URLSearchParams(location.search).get('token') || '';
const A = (u) => u + (TOKEN ? (u.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(TOKEN) : '');
const $ = id => document.getElementById(id);
const toast = (m) => { const t=$('toast'); t.textContent=m; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),1800); };

async function load() {
  const r = await fetch(A('/admin/config')); CFG = await r.json();
  const a = CFG.autoreply || {}, llm = a.llm || {}, ty = a.typing || {}, sp = a.split || {};
  $('enabled').checked = !!a.enabled; $('cooldown').value = a.cooldown ?? 2;
  $('reply_private').checked = !!a.reply_private; $('reply_group').checked = !!a.reply_group;
  $('group_at_only').checked = !!a.group_at_only; $('group_reply_probability').value = a.group_reply_probability ?? 1;
  $('fallback').value = a.fallback || '';
  $('typing_enabled').checked = !!ty.enabled; $('per_char_ms').value = ty.per_char_ms ?? 55; $('max_ms').value = ty.max_ms ?? 5000;
  $('split_enabled').checked = !!sp.enabled; $('max_segments').value = sp.max_segments ?? 3;
  $('llm_enabled').checked = !!llm.enabled; $('base_url').value = llm.base_url || '';
  $('api_key').value = llm.api_key || ''; $('model').value = llm.model || '';
  $('temperature').value = llm.temperature ?? 0.95; $('history').value = llm.history ?? 10;
  $('persona').value = llm.persona || '';
  const st = await (await fetch(A('/status'))).json();
  const s = $('status');
  s.textContent = st.connected ? '已连接 QQ' : '未连接';
  s.className = 'badge' + (st.connected ? ' on' : '');
  $('meta').textContent = `账号 ${st.self_id || '-'} · 适配器 ${st.adapter} · 插件 ${st.plugins}`;
}

function collect() {
  const a = JSON.parse(JSON.stringify(CFG.autoreply || {}));
  a.enabled = $('enabled').checked; a.cooldown = +$('cooldown').value;
  a.reply_private = $('reply_private').checked; a.reply_group = $('reply_group').checked;
  a.group_at_only = $('group_at_only').checked; a.group_reply_probability = +$('group_reply_probability').value;
  a.fallback = $('fallback').value;
  a.typing = Object.assign({}, a.typing, {enabled:$('typing_enabled').checked, per_char_ms:+$('per_char_ms').value, max_ms:+$('max_ms').value});
  a.split = Object.assign({}, a.split, {enabled:$('split_enabled').checked, max_segments:+$('max_segments').value});
  a.llm = Object.assign({}, a.llm, {
    enabled:$('llm_enabled').checked, base_url:$('base_url').value, api_key:$('api_key').value,
    model:$('model').value, temperature:+$('temperature').value, history:+$('history').value, persona:$('persona').value
  });
  return a;
}

async function save() {
  const r = await fetch(A('/admin/save'), {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({autoreply: collect()})});
  const d = await r.json();
  if (d.ok) { CFG.autoreply = collect(); $('saved').textContent = '已保存 ' + new Date().toLocaleTimeString(); toast('已保存，立即生效'); }
  else toast('保存失败: ' + (d.error||''));
}

async function loadModels() {
  $('testout').textContent = '拉取中…';
  const r = await fetch(A('/admin/models')); const d = await r.json();
  if (!d.ok) { $('testout').textContent = '拉取失败: ' + (d.error||''); return; }
  const dl = $('models'); dl.innerHTML = '';
  d.models.forEach(m => { const o = document.createElement('option'); o.value = m; dl.appendChild(o); });
  $('testout').textContent = '共 ' + d.models.length + ' 个模型：\n' + d.models.join(', ');
}

async function testChat() {
  $('testout').textContent = '生成中…';
  const r = await fetch(A('/admin/test'), {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text: $('testin').value, autoreply: collect()})});
  const d = await r.json();
  $('testout').textContent = d.ok ? (d.reply || '(空回复)') + `\n\n— ${d.model} · ${d.ms}ms` : '出错: ' + (d.error||'');
}

load();
</script>
</body>
</html>
"""


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
