"""qq-bridge 综合控制台：独立进程常驻 8089，机器人停了它还在。

功能：
  概览   —— 服务/QQ/协议端状态，启动·停止·重启
  设置   —— 模型、人设、行为、记忆、心情、表情包、主动开聊，保存后热重载
  记忆   —— 查看每个会话记得什么，可清空
  日志   —— 直接看服务日志尾巴
  试聊   —— 用当前设置跑一遍 AI，不发给 QQ

启动： .venv\\Scripts\\pythonw.exe console.py   访问： http://127.0.0.1:8089
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

import yaml
from aiohttp import ClientSession, web

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from qqbot.admin import PAGE as LEGACY_PAGE  # noqa: E402,F401  (保留旧页面入口)

CONSOLE_PORT = 8089
BOT_PORT = 8088
NAPCAT_PORT = 6099
STARTED_AT = time.time()

log = logging.getLogger("console")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")


# ---------------------------------------------------------------- 基础设施
def load_cfg() -> dict:
    p = ROOT / "config.yaml"
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def save_cfg(raw: dict) -> None:
    p = ROOT / "config.yaml"
    if p.exists():
        (ROOT / "config.yaml.bak").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    p.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")


async def port_open(port: int) -> bool:
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), timeout=1.5)
        writer.close()
        return True
    except Exception:
        return False


async def bot_status() -> dict:
    try:
        async with ClientSession() as s:
            async with s.get(f"http://127.0.0.1:{BOT_PORT}/status", timeout=3) as r:
                return await r.json(content_type=None)
    except Exception as exc:
        return {"ok": False, "connected": False, "error": str(exc)}


def qq_running() -> bool:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq QQ.exe"], capture_output=True, text=True, timeout=10
        ).stdout
        return "QQ.exe" in out
    except Exception:
        return False


def run_script(*args: str) -> None:
    subprocess.Popen(
        [*args],
        cwd=str(ROOT),
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def start_all() -> str:
    if (ROOT / "start_silent.vbs").exists():
        run_script("wscript.exe", str(ROOT / "start_silent.vbs"))
        return "已发送启动指令"
    return "找不到 start_silent.vbs"


def stop_all() -> str:
    subprocess.run(["cmd", "/c", str(ROOT / "stop_all.bat")], cwd=str(ROOT), capture_output=True, timeout=60)
    return "已停止"


def tail(path: Path, n: int = 200) -> str:
    if not path.exists():
        return "（没有日志文件）"
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return "\n".join(lines[-n:])
    except Exception as exc:
        return f"读取失败: {exc!r}"


# ---------------------------------------------------------------- 接口
async def api_status(request: web.Request) -> web.Response:
    bot = await bot_status()
    return web.json_response(
        {
            "bot": bot,
            "bot_up": await port_open(BOT_PORT),
            "qq_up": qq_running(),
            "napcat_up": await port_open(NAPCAT_PORT),
            "console_uptime": int(time.time() - STARTED_AT),
        }
    )


async def api_start(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "msg": start_all()})


async def api_stop(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "msg": stop_all()})


async def api_restart(request: web.Request) -> web.Response:
    stop_all()
    await asyncio.sleep(3)
    return web.json_response({"ok": True, "msg": start_all()})


async def api_config(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "config": load_cfg()})


async def api_config_save(request: web.Request) -> web.Response:
    data = await request.json()
    cfg = data.get("config") or {}
    if not isinstance(cfg, dict) or not cfg:
        return web.json_response({"ok": False, "error": "config 为空"})
    save_cfg(cfg)
    reloaded = False
    try:
        async with ClientSession() as s:
            async with s.post(f"http://127.0.0.1:{BOT_PORT}/admin/reload", timeout=5) as r:
                reloaded = bool((await r.json(content_type=None)).get("ok"))
    except Exception:
        pass
    return web.json_response({"ok": True, "reloaded": reloaded})


async def api_test(request: web.Request) -> web.Response:
    from qqbot.admin import test_llm

    data = await request.json()
    ar = (load_cfg().get("autoreply") or {})
    if data.get("config"):
        ar = (data["config"].get("autoreply") or ar)
    return web.json_response(await test_llm(ar, data.get("text") or "在吗"))


async def api_models(request: web.Request) -> web.Response:
    from qqbot.admin import list_models

    return web.json_response(await list_models(load_cfg().get("autoreply") or {}))


def _store():
    from qqbot.personas import PersonaStore

    root = ((load_cfg().get("autoreply") or {}).get("memory") or {}).get("root") or "data"
    return PersonaStore(root)


async def api_personas(request: web.Request) -> web.Response:
    st = _store()
    data = st.load()
    return web.json_response({"ok": True, "active": st.active_id(), "personas": data.get("personas") or []})


async def api_personas_save(request: web.Request) -> web.Response:
    data = await request.json()
    personas = data.get("personas") or []
    clean = []
    for p in personas:
        pid = str(p.get("id") or "").strip()
        if not pid:
            continue
        clean.append({"id": pid, "name": str(p.get("name") or pid), "prompt": str(p.get("prompt") or "")})
    if not clean:
        return web.json_response({"ok": False, "error": "至少要有一个有 id 的人格"})
    st = _store()
    cur = st.load()
    active = cur.get("active")
    st.save({"active": active if any(p["id"] == active for p in clean) else clean[0]["id"], "personas": clean})
    return web.json_response({"ok": True})


async def api_personas_active(request: web.Request) -> web.Response:
    data = await request.json()
    ok = _store().set_active(str(data.get("id") or ""))
    return web.json_response({"ok": ok})


async def api_backups(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "backups": _store().backups()})


async def api_backup_now(request: web.Request) -> web.Response:
    st = _store()
    keep = int(((load_cfg().get("autoreply") or {}).get("memory") or {}).get("backup_keep") or 20)
    made = st.backup(keep=keep)
    return web.json_response({"ok": True, "count": len(made), "files": made})


async def api_restore(request: web.Request) -> web.Response:
    data = await request.json()
    return web.json_response(_store().restore(str(data.get("file") or "")))


async def api_memory(request: web.Request) -> web.Response:
    from qqbot import mood as mood_mod

    st = _store()
    chat = request.query.get("chat")
    if not chat:
        chats = []
        for p in st.personas():
            mem = st.memory(p["id"])
            for cid in mem.known_chats(30):
                s = mem.get_state("__persona__")
                chats.append(
                    {
                        "chat": cid,
                        "persona": p.get("name"),
                        "persona_id": p["id"],
                        "count": mem.message_count(cid),
                        "mood": mood_mod.label(s.get("mood") or {}),
                        "last": mem.last_ts(cid),
                    }
                )
        chats.sort(key=lambda c: c["last"], reverse=True)
        return web.json_response({"ok": True, "chats": chats})

    pid = request.query.get("persona") or st.chat_persona(chat)
    mem = st.memory(pid)
    s = mem.get_state("__persona__")
    return web.json_response(
        {
            "ok": True,
            "chat": chat,
            "persona": (st.get(pid) or {}).get("name", pid),
            "count": mem.message_count(chat),
            "mood": mood_mod.label(s.get("mood") or {}),
            "mood_raw": s.get("mood") or {},
            "traits": s.get("traits") or {},
            "summary": mem.get_summary(chat),
            "facts": mem.facts(chat),
            "recent": mem.recent(chat, 30),
        }
    )


async def api_forget(request: web.Request) -> web.Response:
    data = await request.json()
    chat = data.get("chat")
    if not chat:
        return web.json_response({"ok": False, "error": "缺 chat"})
    st = _store()
    pid = data.get("persona") or st.chat_persona(chat)
    st.memory(pid).forget(chat)
    return web.json_response({"ok": True})


async def api_logs(request: web.Request) -> web.Response:
    n = int(request.query.get("n") or 200)
    return web.Response(text=tail(ROOT / "logs" / "qq-bridge.log", n), content_type="text/plain", charset="utf-8")


async def index(request: web.Request) -> web.Response:
    return web.Response(text=PANEL, content_type="text/html", charset="utf-8")


PANEL = r"""<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>qq-bridge 控制台</title>
<style>
:root{--bg:#0e1116;--card:#171b23;--line:#252b36;--fg:#e7eaf0;--dim:#8892a4;--acc:#4f7cff;--ok:#31c48d;--bad:#f0553f;--warn:#f0b429}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
header{display:flex;align-items:center;gap:14px;padding:16px 24px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:5}
h1{font-size:17px;margin:0}
.dots{display:flex;gap:14px;margin-left:auto;font-size:12px;color:var(--dim);align-items:center}
.dot{display:inline-flex;align-items:center;gap:6px}
.dot i{width:8px;height:8px;border-radius:50%;background:#3a4150;display:inline-block}
.dot.on i{background:var(--ok);box-shadow:0 0 8px rgba(49,196,141,.7)}
nav{display:flex;gap:4px;padding:0 24px;border-bottom:1px solid var(--line)}
nav button{background:none;border:0;color:var(--dim);padding:12px 14px;font:inherit;cursor:pointer;border-bottom:2px solid transparent}
nav button.active{color:var(--fg);border-bottom-color:var(--acc)}
main{padding:22px 24px;max-width:1080px}
section{display:none}section.active{display:block}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:16px}
.card h2{font-size:13px;color:var(--dim);margin:0 0 14px;letter-spacing:.5px}
.row{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px}
.field{flex:1;min-width:170px}
label{display:block;font-size:12px;color:var(--dim);margin-bottom:5px}
input[type=text],input[type=number],textarea,select{width:100%;padding:9px 11px;background:#0c1016;border:1px solid var(--line);border-radius:9px;color:var(--fg);font:13px/1.6 inherit}
textarea{min-height:130px;resize:vertical}
.sw{display:flex;align-items:center;gap:8px;font-size:13px}
.sw input{width:16px;height:16px;accent-color:var(--acc)}
button.act{padding:9px 16px;border:0;border-radius:9px;background:var(--acc);color:#fff;font-weight:600;font-size:13px;cursor:pointer}
button.act.ghost{background:#232a36;color:var(--fg)}
button.act.danger{background:#3a1f1c;color:#ff8f7a}
button.act:active{transform:translateY(1px)}
pre{background:#0a0d13;border:1px solid var(--line);border-radius:10px;padding:14px;font-size:12.5px;overflow:auto;max-height:520px;white-space:pre-wrap;margin:0}
.kv{display:grid;grid-template-columns:120px 1fr;gap:8px 14px;font-size:13px}
.kv b{color:var(--dim);font-weight:400}
.hint{font-size:12px;color:var(--dim)}
.pill{font-size:12px;padding:2px 9px;border-radius:20px;background:#232a36;color:var(--dim)}
.pill.ok{background:rgba(49,196,141,.15);color:var(--ok)}
.pill.bad{background:rgba(240,85,63,.15);color:var(--bad)}
.chatline{display:flex;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid var(--line);font-size:13px;cursor:pointer}
.chatline:hover{color:var(--acc)}
.toast{position:fixed;right:20px;bottom:20px;background:var(--ok);color:#06281c;padding:10px 16px;border-radius:10px;font-weight:600;opacity:0;transition:.25s}
.toast.show{opacity:1}
</style></head>
<body>
<header>
  <h1>qq-bridge 控制台</h1>
  <span class="pill" id="acc">-</span>
  <div class="dots">
    <span class="dot" id="d-bot"><i></i>服务</span>
    <span class="dot" id="d-qq"><i></i>QQ</span>
    <span class="dot" id="d-nc"><i></i>协议端</span>
  </div>
</header>
<nav>
  <button class="active" data-t="home">概览</button>
  <button data-t="cfg">设置</button>
  <button data-t="persona">人格</button>
  <button data-t="mem">记忆</button>
  <button data-t="backup">备份</button>
  <button data-t="test">试聊</button>
  <button data-t="log">日志</button>
</nav>
<main>
  <section id="home" class="active">
    <div class="card">
      <h2>进程控制</h2>
      <div class="row">
        <button class="act" onclick="act('start')">启动</button>
        <button class="act danger" onclick="act('stop')">停止</button>
        <button class="act ghost" onclick="act('restart')">重启</button>
        <button class="act ghost" onclick="loadStatus()">刷新状态</button>
      </div>
      <div class="kv">
        <b>机器人服务</b><span id="s-bot">-</span>
        <b>QQ / 协议端</b><span id="s-nc">-</span>
        <b>登录账号</b><span id="s-acc">-</span>
        <b>插件</b><span id="s-plug">-</span>
        <b>控制台已运行</b><span id="s-up">-</span>
      </div>
    </div>
    <div class="card">
      <h2>外部入口</h2>
      <div class="kv">
        <b>NapCat WebUI</b><span><a href="#" id="link-nc" style="color:var(--acc)">打开（需 token）</a></span>
        <b>发送接口</b><span>http://127.0.0.1:8088/send/*</span>
        <b>反向 WS</b><span>ws://127.0.0.1:8199/onebot/v11/ws</span>
      </div>
    </div>
  </section>

  <section id="cfg">
    <div class="card">
      <h2>模型</h2>
      <div class="row">
        <div class="field" style="flex:2"><label>模型</label><input type="text" id="c_model" list="models"><datalist id="models"></datalist></div>
        <div class="field"><label>温度</label><input type="number" id="c_temp" step="0.05" min="0" max="2"></div>
        <div class="field"><label>记忆轮数</label><input type="number" id="c_hist" min="0" max="40"></div>
      </div>
      <div class="row">
        <div class="field" style="flex:2"><label>base_url</label><input type="text" id="c_base"></div>
        <div class="field" style="flex:2"><label>API Key</label><input type="text" id="c_key"></div>
      </div>
      <div class="row"><div class="field"><label>人设（说话风格，最重要）</label><textarea id="c_persona"></textarea></div></div>
      <div class="row" style="margin-bottom:0"><button class="act ghost" onclick="fetchModels()">拉取模型列表</button></div>
    </div>
    <div class="card">
      <h2>行为</h2>
      <div class="row">
        <div class="field"><label class="sw"><input type="checkbox" id="c_enabled">启用自动回复</label></div>
        <div class="field"><label class="sw"><input type="checkbox" id="c_llm">启用 AI</label></div>
        <div class="field"><label class="sw"><input type="checkbox" id="c_typing">模拟打字</label></div>
        <div class="field"><label class="sw"><input type="checkbox" id="c_split">长回复分段</label></div>
      </div>
      <div class="row">
        <div class="field"><label class="sw"><input type="checkbox" id="c_priv">回私聊</label></div>
        <div class="field"><label class="sw"><input type="checkbox" id="c_grp">回群聊</label></div>
        <div class="field"><label class="sw"><input type="checkbox" id="c_at">群里只回@</label></div>
        <div class="field"><label>冷却秒</label><input type="number" id="c_cd" step="0.5" min="0"></div>
      </div>
      <div class="row" style="margin-bottom:0">
        <div class="field"><label class="sw"><input type="checkbox" id="c_wl">只理白名单</label></div>
        <div class="field" style="flex:2"><label>白名单 QQ 号（逗号分隔）</label><input type="text" id="c_wl_users" placeholder="2966763558"></div>
        <div class="field" style="flex:2"><label>白名单群号（逗号分隔）</label><input type="text" id="c_wl_groups"></div>
      </div>
    </div>
    <div class="card">
      <h2>记忆 · 心情 · 表情包 · 上网</h2>
      <div class="row">
        <div class="field"><label class="sw"><input type="checkbox" id="c_mem">长期记忆</label></div>
        <div class="field"><label>复盘间隔(条)</label><input type="number" id="c_reflect" min="0"></div>
        <div class="field"><label>普通记忆保留(天)</label><input type="number" id="c_retain" min="1" max="365"></div>
        <div class="field"><label class="sw"><input type="checkbox" id="c_mood">有心情</label></div>
        <div class="field"><label class="sw"><input type="checkbox" id="c_web">会上网</label></div>
      </div>
      <div class="row" style="margin-bottom:0">
        <div class="field"><label class="sw"><input type="checkbox" id="c_sticker">发表情包</label></div>
        <div class="field"><label>表情包概率</label><input type="number" id="c_stk_p" step="0.05" min="0" max="1"></div>
      </div>
    </div>
    <div class="card">
      <h2>主动开聊</h2>
      <div class="row">
        <div class="field"><label class="sw"><input type="checkbox" id="c_pa">启用</label></div>
        <div class="field" style="flex:2"><label>目标（u=私聊号 g=群号，逗号分隔）</label><input type="text" id="c_pa_targets"></div>
      </div>
      <div class="row">
        <div class="field"><label>最短间隔(分)</label><input type="number" id="c_pa_min" min="5"></div>
        <div class="field"><label>最长间隔(分)</label><input type="number" id="c_pa_max" min="5"></div>
        <div class="field"><label>每天上限</label><input type="number" id="c_pa_cap" min="1"></div>
      </div>
      <div class="row" style="margin-bottom:0">
        <div class="field"><label>安静时段起(时)</label><input type="number" id="c_pa_qs" min="0" max="23"></div>
        <div class="field"><label>安静时段止(时)</label><input type="number" id="c_pa_qe" min="0" max="23"></div>
        <div class="field"><label>带表情包概率</label><input type="number" id="c_pa_stk" step="0.05" min="0" max="1"></div>
        <div class="field"><label>带链接概率</label><input type="number" id="c_pa_link" step="0.05" min="0" max="1"></div>
      </div>
    </div>
    <div class="row" style="margin-bottom:26px">
      <button class="act" onclick="saveCfg()">保存并热重载</button>
      <span class="hint" id="save-hint"></span>
    </div>
  </section>

  <section id="persona">
    <div class="card">
      <h2>多重人格（每个人格记忆独立，QQ 里发「切换人格 名字」即可切）</h2>
      <div id="plist" class="hint">加载中…</div>
      <div class="row" style="margin:14px 0 0">
        <button class="act ghost" onclick="addPersona()">新增人格</button>
        <button class="act" onclick="savePersonas()">保存人格</button>
        <span class="hint" id="p-hint"></span>
      </div>
    </div>
  </section>

  <section id="mem">
    <div class="card"><h2>会话列表</h2><div id="chats" class="hint">加载中…</div></div>
    <div class="card"><h2>会话详情</h2><div id="memdetail" class="hint">点上面某一行查看</div></div>
  </section>

  <section id="backup">
    <div class="card">
      <h2>记忆备份（自动每 6 小时一份，保留最近 20 份）</h2>
      <div class="row">
        <button class="act" onclick="doBackup()">立刻备份</button>
        <button class="act ghost" onclick="loadBackups()">刷新列表</button>
        <span class="hint">备份是 SQLite 在线快照，不锁库</span>
      </div>
      <div id="blist" class="hint">加载中…</div>
    </div>
  </section>

  <section id="test">
    <div class="card">
      <h2>试聊（不发给 QQ）</h2>
      <div class="row">
        <div class="field" style="flex:3"><input type="text" id="t_in" value="你是谁啊 怎么突然加我"></div>
        <button class="act" onclick="runTest()">发送</button>
      </div>
      <pre id="t_out">（还没测）</pre>
    </div>
  </section>

  <section id="log">
    <div class="card">
      <h2>服务日志</h2>
      <div class="row"><button class="act ghost" onclick="loadLog()">刷新</button><span class="hint">logs/qq-bridge.log 最后 200 行</span></div>
      <pre id="logbox">加载中…</pre>
    </div>
  </section>
</main>
<div class="toast" id="toast"></div>
<script>
const $=id=>document.getElementById(id);
const toast=m=>{const t=$('toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),1800)};
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('section').forEach(x=>x.classList.remove('active'));
  b.classList.add('active'); $(b.dataset.t).classList.add('active');
  if(b.dataset.t==='mem') loadChats();
  if(b.dataset.t==='log') loadLog();
  if(b.dataset.t==='persona') loadPersonas();
  if(b.dataset.t==='backup') loadBackups();
  if(b.dataset.t==='cfg' && !CFG_LOADED) loadCfg();
});
let CFG={}, CFG_LOADED=false;
let PERSONAS={active:'',personas:[]};
function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;')}

async function loadPersonas(){
  PERSONAS = await (await fetch('/api/personas')).json();
  renderPersonas();
}
function renderPersonas(){
  const box=$('plist');
  if(!PERSONAS.personas || !PERSONAS.personas.length){box.textContent='还没有人格，点下面新增';return}
  box.innerHTML = PERSONAS.personas.map((p,i)=>`
   <div class="card" style="background:#10141b;margin-bottom:12px">
     <div class="row">
       <div class="field"><label>名字</label><input type="text" id="pn_${i}" value="${esc(p.name)}"></div>
       <div class="field"><label>id（英文）</label><input type="text" id="pi_${i}" value="${esc(p.id)}"></div>
       <div class="field"><label>状态</label><div class="hint" style="padding-top:8px">${p.id===PERSONAS.active?'✅ 默认使用中':''}</div></div>
     </div>
     <div class="row"><div class="field"><label>人设</label><textarea id="pp_${i}" style="min-height:88px">${esc(p.prompt||'')}</textarea></div></div>
     <div class="row" style="margin-bottom:0">
       <button class="act ghost" onclick="setActive('${p.id}')">设为默认</button>
       <button class="act danger" onclick="delPersona(${i})">删除</button>
     </div>
   </div>`).join('');
}
function addPersona(){
  PERSONAS.personas.push({id:'p'+Date.now().toString().slice(-5),name:'新人格',prompt:''});
  renderPersonas();
}
function delPersona(i){ PERSONAS.personas.splice(i,1); renderPersonas(); }
function collectPersonas(){
  const out=[];
  PERSONAS.personas.forEach((p,i)=>{
    const id=$('pi_'+i), nm=$('pn_'+i), pr=$('pp_'+i);
    if(!id) return;
    out.push({id:id.value.trim(),name:nm.value.trim(),prompt:pr.value});
  });
  return out;
}
async function savePersonas(){
  const r=await (await fetch('/api/personas',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({personas:collectPersonas()})})).json();
  if(r.ok){$('p-hint').textContent='已保存 '+new Date().toLocaleTimeString();toast('人格已保存');loadPersonas()}
  else toast('保存失败: '+(r.error||''));
}
async function setActive(pid){
  await fetch('/api/personas/active',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:pid})});
  toast('默认人格已切换');loadPersonas();
}
async function loadBackups(){
  const r=await (await fetch('/api/backups')).json();
  const box=$('blist');
  if(!r.ok||!r.backups.length){box.textContent='还没有备份';return}
  box.innerHTML=r.backups.map(b=>`<div class="chatline"><span class="pill">${b.persona_name}</span>
    <span>${b.file}</span><span class="hint">${(b.size/1024).toFixed(0)} KB</span>
    <span class="hint" style="margin-left:auto">${new Date(b.time*1000).toLocaleString()}</span>
    <button class="act ghost" style="padding:4px 10px" onclick="doRestore('${b.file}')">恢复</button></div>`).join('');
}
async function doBackup(){
  const r=await (await fetch('/api/backup',{method:'POST'})).json();
  toast(r.ok? ('已备份 '+r.count+' 份') : '备份失败'); loadBackups();
}
async function doRestore(file){
  if(!confirm('用 '+file+' 覆盖当前记忆？会先给现在的库留一份安全备份。')) return;
  const r=await (await fetch('/api/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file})})).json();
  toast(r.ok?'已恢复':'恢复失败: '+(r.error||'')); loadBackups();
}

async function loadStatus(){
  const d = await (await fetch('/api/status')).json();
  $('d-bot').className = 'dot'+(d.bot_up?' on':'');
  $('d-qq').className = 'dot'+(d.qq_up?' on':'');
  $('d-nc').className = 'dot'+(d.napcat_up?' on':'');
  $('s-bot').textContent = d.bot_up? '运行中' : '未运行';
  $('s-nc').textContent = (d.qq_up?'QQ ':'') + (d.napcat_up? '协议端在线' : (d.qq_up?'':'未启动'));
  const b = d.bot||{};
  const acc = $('acc');
  acc.textContent = b.connected? ('已连接 '+(b.self_id||'')) : '未连接';
  acc.className = 'pill '+(b.connected?'ok':'bad');
  $('s-acc').textContent = b.self_id || '-';
  $('s-plug').textContent = b.plugins ?? '-';
  $('s-up').textContent = Math.round(d.console_uptime/60)+' 分钟';
  $('link-nc').href = 'http://127.0.0.1:6099/webui';
}
async function act(what){
  toast(what==='stop'?'正在停止…':'正在启动…');
  await fetch('/api/'+what,{method:'POST'});
  setTimeout(()=>{loadStatus();toast('已'+({start:'启动',stop:'停止',restart:'重启'}[what]||what))}, what==='stop'?2000:6000);
}
function val(id){return $(id).value}
function chk(id){return $(id).checked}
function num(id){return +$(id).value}

async function loadCfg(){
  const r = await (await fetch('/api/config')).json();
  CFG = r.config||{}; const a=CFG.autoreply||{}, llm=a.llm||{}, ty=a.typing||{}, sp=a.split||{}, me=a.memory||{}, mo=a.mood||{}, we=a.web||{}, st=a.stickers||{}, pa=a.proactive||{};
  $('c_model').value=llm.model||''; $('c_temp').value=llm.temperature??0.95; $('c_hist').value=llm.history??12;
  $('c_base').value=llm.base_url||''; $('c_key').value=llm.api_key||''; $('c_persona').value=llm.persona||'';
  $('c_enabled').checked=!!a.enabled; $('c_llm').checked=!!llm.enabled; $('c_typing').checked=!!ty.enabled; $('c_split').checked=!!sp.enabled;
  $('c_priv').checked=!!a.reply_private; $('c_grp').checked=!!a.reply_group; $('c_at').checked=!!a.group_at_only; $('c_cd').value=a.cooldown??2;
  const wl=a.whitelist||{};
  $('c_wl').checked=wl.enabled!==false;
  $('c_wl_users').value=(wl.users||[]).join(',');
  $('c_wl_groups').value=(wl.groups||[]).join(',');
  $('c_mem').checked=me.enabled!==false; $('c_reflect').value=me.reflect_every??12; $('c_mood').checked=mo.enabled!==false; $('c_web').checked=we.enabled!==false;
  $('c_sticker').checked=st.enabled!==false; $('c_stk_p').value=st.probability??0.35;
  $('c_pa').checked=!!pa.enabled; $('c_pa_targets').value=(pa.targets||[]).join(',');
  $('c_pa_min').value=pa.min_minutes??45; $('c_pa_max').value=pa.max_minutes??180; $('c_pa_cap').value=pa.max_per_day??6;
  $('c_pa_qs').value=pa.quiet_start??23; $('c_pa_qe').value=pa.quiet_end??8;
  $('c_pa_stk').value=pa.sticker_probability??0.4; $('c_pa_link').value=pa.link_probability??0.15;
  CFG_LOADED=true;
}
async function saveCfg(){
  const a = CFG.autoreply || {};
  a.enabled=chk('c_enabled');
  a.cooldown=num('c_cd'); a.reply_private=chk('c_priv'); a.reply_group=chk('c_grp'); a.group_at_only=chk('c_at');
  a.whitelist={enabled:chk('c_wl'),
    users:val('c_wl_users').split(',').map(s=>s.trim()).filter(Boolean),
    groups:val('c_wl_groups').split(',').map(s=>s.trim()).filter(Boolean)};
  a.typing=Object.assign({},a.typing,{enabled:chk('c_typing')});
  a.split=Object.assign({},a.split,{enabled:chk('c_split')});
  a.llm=Object.assign({},a.llm,{enabled:chk('c_llm'),model:val('c_model'),temperature:num('c_temp'),history:num('c_hist'),base_url:val('c_base'),api_key:val('c_key'),persona:val('c_persona')});
  a.memory=Object.assign({},a.memory,{enabled:chk('c_mem'),reflect_every:num('c_reflect')});
  a.mood=Object.assign({},a.mood,{enabled:chk('c_mood')});
  a.web=Object.assign({},a.web,{enabled:chk('c_web')});
  a.stickers=Object.assign({},a.stickers,{enabled:chk('c_sticker'),probability:num('c_stk_p')});
  a.proactive=Object.assign({},a.proactive,{enabled:chk('c_pa'),targets:val('c_pa_targets').split(',').map(s=>s.trim()).filter(Boolean),
    min_minutes:num('c_pa_min'),max_minutes:num('c_pa_max'),max_per_day:num('c_pa_cap'),
    quiet_start:num('c_pa_qs'),quiet_end:num('c_pa_qe'),sticker_probability:num('c_pa_stk'),link_probability:num('c_pa_link')});
  CFG.autoreply = a;
  const r = await (await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({config:CFG})})).json();
  if(r.ok){ $('save-hint').textContent='已保存 '+(r.reloaded?'并热重载':'（机器人未运行，下次启动生效）'); toast('已保存'); }
  else toast('保存失败');
}
async function fetchModels(){
  const r = await (await fetch('/api/models')).json();
  if(!r.ok) return toast('拉取失败: '+(r.error||''));
  const dl=$('models'); dl.innerHTML='';
  r.models.forEach(m=>{const o=document.createElement('option');o.value=m;dl.appendChild(o)});
  toast('共 '+r.models.length+' 个模型，点模型框选');
}
async function loadChats(){
  const r = await (await fetch('/api/memory')).json();
  const box=$('chats');
  if(!r.ok||!r.chats.length){box.textContent='还没有记忆（先聊几句）';return}
  box.innerHTML = r.chats.map(c=>`<div class="chatline" onclick="loadMem('${c.chat}')">
     <span class="pill">${c.chat}</span><span>${c.count} 条</span><span class="hint">${c.mood}</span>
     <span class="hint" style="margin-left:auto">${new Date(c.last*1000).toLocaleString()}</span></div>`).join('');
}
async function loadMem(chat){
  const d = await (await fetch('/api/memory?chat='+encodeURIComponent(chat))).json();
  const facts = Object.entries(d.facts||{}).map(([k,v])=>`${k}：${v}`).join('；')||'无';
  const traits = Object.entries(d.traits||{}).map(([k,v])=>`${k} ${v}`).join('，')||'还在养成';
  const recent = (d.recent||[]).map(m=>`<div style="color:${m.role==='user'?'#cbd5e1':'#8ab4ff'}">${m.role==='user'?'对方':'我'}：${m.content}</div>`).join('');
  $('memdetail').innerHTML = `<div class="kv">
     <b>会话</b><span>${d.chat}</span>
     <b>记忆条数</b><span>${d.count}</span>
     <b>心情</b><span>${d.mood}</span>
     <b>性格</b><span>${traits}</span>
     <b>摘要</b><span>${d.summary||'无'}</span>
     <b>记得的事</b><span>${facts}</span></div>
     <div style="margin:12px 0"><button class="act danger" onclick="forget('${d.chat}')">清空这个会话的记忆</button></div>
     <div style="border-top:1px solid var(--line);padding-top:10px;font-size:13px;line-height:1.9">${recent||'<span class=hint>没有对话</span>'}</div>`;
}
async function forget(chat){
  if(!confirm('确定清空 '+chat+' 的记忆？')) return;
  await fetch('/api/memory/forget',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chat})});
  toast('已清空'); loadChats(); $('memdetail').textContent='已清空';
}
async function runTest(){
  $('t_out').textContent='生成中…';
  const r = await (await fetch('/api/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:val('t_in')})})).json();
  $('t_out').textContent = r.ok? `${r.reply||'(空)'}\n\n— ${r.model} · ${r.ms}ms` : ('出错：'+(r.error||''));
}
async function loadLog(){
  $('logbox').textContent = await (await fetch('/api/logs?n=200')).text();
}
loadStatus(); setInterval(loadStatus, 5000);
</script></body></html>
"""


def main() -> None:
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/api/status", api_status)
    app.router.add_post("/api/start", api_start)
    app.router.add_post("/api/stop", api_stop)
    app.router.add_post("/api/restart", api_restart)
    app.router.add_get("/api/config", api_config)
    app.router.add_post("/api/config", api_config_save)
    app.router.add_post("/api/test", api_test)
    app.router.add_get("/api/models", api_models)
    app.router.add_get("/api/memory", api_memory)
    app.router.add_post("/api/memory/forget", api_forget)
    app.router.add_get("/api/personas", api_personas)
    app.router.add_post("/api/personas", api_personas_save)
    app.router.add_post("/api/personas/active", api_personas_active)
    app.router.add_get("/api/backups", api_backups)
    app.router.add_post("/api/backup", api_backup_now)
    app.router.add_post("/api/restore", api_restore)
    app.router.add_get("/api/logs", api_logs)
    log.info("控制台已启动： http://127.0.0.1:%d", CONSOLE_PORT)
    web.run_app(app, host="127.0.0.1", port=CONSOLE_PORT, print=None)


if __name__ == "__main__":
    main()
