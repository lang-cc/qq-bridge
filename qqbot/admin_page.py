"""网页配置台的页面（唯一后台的 UI）。

单独放一个文件，方便改样式；由 admin.py 导入 PAGE 给 http_api 用。
纯原生 HTML/CSS/JS，不依赖任何 CDN —— 客户机器上断网也能打开。
"""

PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>qq-bridge 控制台</title>
<style>
  :root{
    --bg:#0a0c11; --bg2:#0e1118;
    --surface:#12151d; --surface-2:#161a24;
    --line:#232838; --line-2:#2c3245;
    --fg:#e9ecf3; --dim:#8d96ab; --dim-2:#616b80;
    --acc:#6b8cff; --acc-2:#8f6bff;
    --ok:#3ddc97; --warn:#ffb454; --danger:#ff6b6b;
    --r:16px; --r-sm:10px;
  }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0}
  body{
    background:
      radial-gradient(1100px 520px at 12% -8%, rgba(107,140,255,.13), transparent 62%),
      radial-gradient(900px 460px at 96% 4%, rgba(143,107,255,.10), transparent 58%),
      var(--bg);
    color:var(--fg);
    font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
    -webkit-font-smoothing:antialiased;
    min-height:100vh;
  }
  a{color:var(--acc);text-decoration:none}
  .shell{max-width:1040px;margin:0 auto;padding:0 18px 120px}

  /* ---------- 顶栏 ---------- */
  header{
    position:sticky;top:0;z-index:30;
    display:flex;align-items:center;gap:14px;flex-wrap:wrap;
    padding:14px 0 12px;margin-bottom:6px;
    background:linear-gradient(var(--bg) 62%,rgba(10,12,17,.72));
    backdrop-filter:blur(12px);
  }
  .brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px;letter-spacing:.2px}
  .logo{
    width:28px;height:28px;border-radius:9px;flex:0 0 28px;
    background:linear-gradient(135deg,var(--acc),var(--acc-2));
    box-shadow:0 6px 18px rgba(107,140,255,.35);
    display:grid;place-items:center;font-size:14px;font-weight:800;color:#0a0c11;
  }
  .brand small{font-weight:500;color:var(--dim-2);font-size:12px;margin-left:2px}
  .pill{
    display:inline-flex;align-items:center;gap:7px;
    padding:5px 11px;border-radius:999px;font-size:12px;font-weight:600;
    background:var(--surface-2);border:1px solid var(--line);color:var(--dim);
    white-space:nowrap;
  }
  .pill .dot{width:7px;height:7px;border-radius:50%;background:var(--dim-2);box-shadow:0 0 0 3px rgba(255,255,255,.03)}
  .pill.on{color:var(--ok);border-color:rgba(61,220,151,.32);background:rgba(61,220,151,.10)}
  .pill.on .dot{background:var(--ok);box-shadow:0 0 10px rgba(61,220,151,.7)}
  .pill.off{color:var(--danger);border-color:rgba(255,107,107,.3);background:rgba(255,107,107,.09)}
  .pill.off .dot{background:var(--danger)}
  .spacer{flex:1}

  /* ---------- 标签页 ---------- */
  nav.tabs{
    position:sticky;top:58px;z-index:25;
    display:flex;gap:4px;overflow-x:auto;padding:6px;margin:0 0 18px;
    background:rgba(18,21,29,.86);border:1px solid var(--line);border-radius:14px;
    backdrop-filter:blur(12px);scrollbar-width:none;
  }
  nav.tabs::-webkit-scrollbar{display:none}
  nav.tabs button{
    flex:0 0 auto;border:0;background:transparent;color:var(--dim);
    font:600 13px/1 inherit;padding:10px 16px;border-radius:10px;cursor:pointer;
    transition:.16s;white-space:nowrap;
  }
  nav.tabs button:hover{color:var(--fg);background:rgba(255,255,255,.045)}
  nav.tabs button.active{
    color:#fff;background:linear-gradient(135deg,rgba(107,140,255,.92),rgba(143,107,255,.86));
    box-shadow:0 6px 18px rgba(107,140,255,.28);
  }
  section.tab{display:none;animation:fade .18s ease}
  section.tab.active{display:block}
  @keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}

  /* ---------- 卡片 ---------- */
  .card{
    background:linear-gradient(180deg,rgba(255,255,255,.028),rgba(255,255,255,0)) ,var(--surface);
    border:1px solid var(--line);border-radius:var(--r);
    padding:18px 20px;margin-bottom:14px;
  }
  .card-h{display:flex;align-items:flex-start;gap:12px;margin-bottom:16px}
  .card-h h2{margin:0;font-size:14.5px;font-weight:700;letter-spacing:.2px}
  .card-h p{margin:3px 0 0;font-size:12.5px;color:var(--dim-2);line-height:1.5}
  .card-h .right{margin-left:auto;display:flex;gap:8px;align-items:center}

  /* ---------- 表单 ---------- */
  .grid{display:grid;gap:14px}
  .g2{grid-template-columns:repeat(2,minmax(0,1fr))}
  .g3{grid-template-columns:repeat(3,minmax(0,1fr))}
  .g4{grid-template-columns:repeat(4,minmax(0,1fr))}
  @media (max-width:760px){.g3,.g4{grid-template-columns:repeat(2,minmax(0,1fr))}}
  @media (max-width:520px){.g2,.g3,.g4{grid-template-columns:1fr}}
  label.f{display:block}
  label.f > span{display:block;font-size:12px;color:var(--dim);margin:0 0 6px;font-weight:600}
  label.f small{display:block;color:var(--dim-2);font-size:11.5px;font-weight:400;margin-top:5px}
  input[type=text],input[type=password],input[type=number],textarea,select{
    width:100%;padding:10px 12px;background:var(--bg2);color:var(--fg);
    border:1px solid var(--line);border-radius:var(--r-sm);
    font:13.5px/1.55 inherit;outline:none;transition:.15s;
  }
  input:hover,textarea:hover,select:hover{border-color:var(--line-2)}
  input:focus,textarea:focus,select:focus{
    border-color:var(--acc);box-shadow:0 0 0 3px rgba(107,140,255,.16);background:#0c0f16;
  }
  textarea{min-height:190px;resize:vertical;line-height:1.75}
  .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px}

  /* 开关 */
  .switch{display:flex;align-items:center;justify-content:space-between;gap:12px;
    padding:11px 13px;background:var(--bg2);border:1px solid var(--line);border-radius:var(--r-sm);
    cursor:pointer;transition:.15s;user-select:none}
  .switch:hover{border-color:var(--line-2)}
  .switch span{font-size:13px;font-weight:600}
  .switch input{appearance:none;width:38px;height:22px;border-radius:999px;background:#232a3a;
    position:relative;cursor:pointer;transition:.18s;flex:0 0 38px;margin:0}
  .switch input::after{content:"";position:absolute;top:3px;left:3px;width:16px;height:16px;
    border-radius:50%;background:#7b8499;transition:.18s}
  .switch input:checked{background:linear-gradient(135deg,var(--acc),var(--acc-2))}
  .switch input:checked::after{left:19px;background:#fff}

  /* 按钮 */
  button{font:600 13px/1 inherit;cursor:pointer;border-radius:var(--r-sm);transition:.15s}
  .btn{padding:10px 16px;border:1px solid transparent;color:#fff;
    background:linear-gradient(135deg,var(--acc),var(--acc-2));box-shadow:0 6px 18px rgba(107,140,255,.25)}
  .btn:hover{filter:brightness(1.07)}
  .btn:active{transform:translateY(1px)}
  .btn.ghost{background:var(--surface-2);border-color:var(--line);color:var(--fg);box-shadow:none}
  .btn.ghost:hover{background:#1c2130;border-color:var(--line-2)}
  .btn.danger{background:rgba(255,107,107,.12);border-color:rgba(255,107,107,.34);color:#ff9b9b;box-shadow:none}
  .btn.danger:hover{background:rgba(255,107,107,.2)}
  .btn:disabled{opacity:.5;cursor:not-allowed}
  .btn.sm{padding:8px 12px;font-size:12.5px}

  /* 统计块 */
  .stats{display:grid;gap:12px;grid-template-columns:repeat(4,minmax(0,1fr))}
  @media (max-width:760px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
  .stat{background:var(--bg2);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
  .stat b{display:block;font-size:19px;font-weight:700;letter-spacing:.3px}
  .stat span{display:block;font-size:11.5px;color:var(--dim-2);margin-top:3px}
  .stat.ok b{color:var(--ok)} .stat.bad b{color:var(--danger)}

  /* 记忆 */
  .mem{display:grid;grid-template-columns:236px minmax(0,1fr);gap:14px}
  @media (max-width:760px){.mem{grid-template-columns:1fr}}
  .mem-list{background:var(--bg2);border:1px solid var(--line);border-radius:14px;padding:6px;
    max-height:520px;overflow:auto}
  .mem-item{padding:9px 11px;border-radius:9px;cursor:pointer;font-size:12.5px;color:var(--dim);
    display:flex;justify-content:space-between;gap:8px;transition:.13s}
  .mem-item:hover{background:rgba(255,255,255,.05);color:var(--fg)}
  .mem-item.active{background:rgba(107,140,255,.16);color:#fff}
  .mem-item i{font-style:normal;color:var(--dim-2);font-size:11px}
  .mem-detail{min-width:0}
  .chips{display:flex;flex-wrap:wrap;gap:7px;margin:2px 0 0}
  .chip{font-size:12px;padding:5px 10px;border-radius:999px;background:var(--surface-2);
    border:1px solid var(--line);color:var(--dim)}
  .chip.click{cursor:pointer}
  .chip.click:hover{border-color:var(--acc);color:#fff}
  .bubbles{display:flex;flex-direction:column;gap:8px;max-height:340px;overflow:auto;padding:4px 2px}
  .bub{max-width:82%;padding:9px 13px;border-radius:14px;font-size:13px;line-height:1.6;white-space:pre-wrap;word-break:break-word}
  .bub.me{align-self:flex-end;background:linear-gradient(135deg,rgba(107,140,255,.9),rgba(143,107,255,.82));color:#fff;border-bottom-right-radius:5px}
  .bub.her{align-self:flex-start;background:var(--surface-2);border:1px solid var(--line);border-bottom-left-radius:5px}
  .block-title{font-size:11.5px;font-weight:700;color:var(--dim-2);letter-spacing:.6px;margin:16px 0 8px;text-transform:uppercase}
  .block-title:first-child{margin-top:0}

  /* 日志 */
  .seg{display:inline-flex;gap:3px;padding:3px;background:var(--bg2);border:1px solid var(--line);border-radius:11px}
  .seg button{border:0;background:transparent;color:var(--dim);padding:8px 13px;border-radius:8px;font-size:12.5px;font-weight:600}
  .seg button.active{background:var(--surface-2);color:#fff;box-shadow:0 2px 8px rgba(0,0,0,.25)}
  pre.log{margin:0;background:#080a0f;border:1px solid var(--line);border-radius:12px;padding:14px;
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;line-height:1.65;
    color:#b7c0d4;max-height:58vh;overflow:auto;white-space:pre-wrap;word-break:break-all}
  pre.log::-webkit-scrollbar,.bubbles::-webkit-scrollbar,.mem-list::-webkit-scrollbar{width:9px;height:9px}
  pre.log::-webkit-scrollbar-thumb,.bubbles::-webkit-scrollbar-thumb,.mem-list::-webkit-scrollbar-thumb{
    background:#2b3244;border-radius:9px}
  .hint{font-size:12px;color:var(--dim-2);line-height:1.6}
  .out{margin:0;background:#080a0f;border:1px solid var(--line);border-radius:12px;padding:13px;
    font:12.5px/1.7 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:#c3cbdc;
    white-space:pre-wrap;word-break:break-word;max-height:300px;overflow:auto}

  /* 底部保存条 */
  .savebar{
    position:fixed;left:0;right:0;bottom:0;z-index:40;display:none;gap:12px;align-items:center;
    padding:12px 18px;background:rgba(12,15,22,.9);border-top:1px solid var(--line);
    backdrop-filter:blur(14px);
  }
  .savebar.show{display:flex}
  .savebar .inner{max-width:1040px;margin:0 auto;display:flex;gap:12px;align-items:center;width:100%}
  .savebar .status{font-size:12.5px;color:var(--dim)}

  .toast{
    position:fixed;right:18px;bottom:74px;z-index:60;
    padding:11px 16px;border-radius:12px;font-size:13px;font-weight:600;
    background:linear-gradient(135deg,var(--ok),#25b579);color:#06281c;
    opacity:0;transform:translateY(8px);transition:.22s;pointer-events:none;
    box-shadow:0 10px 26px rgba(0,0,0,.35);max-width:min(90vw,420px);
  }
  .toast.show{opacity:1;transform:none}
  .toast.err{background:linear-gradient(135deg,#ff8b8b,#ff6b6b);color:#3a0b0b}
</style>
</head>
<body>
<div class="shell">

  <header>
    <div class="brand"><div class="logo">Q</div>qq-bridge <small>控制台</small></div>
    <span class="pill" id="pill-conn"><span class="dot"></span><span id="pill-txt">连接中…</span></span>
    <span class="pill" id="pill-acct">账号 —</span>
    <span class="spacer"></span>
    <button class="btn ghost sm" onclick="act('/admin/login','扫码登录')">扫码登录</button>
    <button class="btn ghost sm" onclick="act('/admin/restart','重启服务')">重启</button>
  </header>

  <nav class="tabs">
    <button class="active" data-tab="ov">概览</button>
    <button data-tab="llm">模型与人格</button>
    <button data-tab="beh">行为</button>
    <button data-tab="mem">记忆</button>
    <button data-tab="log">日志</button>
    <button data-tab="chat">试聊</button>
  </nav>

  <!-- ============ 概览 ============ -->
  <section class="tab active" id="tab-ov">
    <div class="stats" style="margin-bottom:14px">
      <div class="stat" id="st-conn"><b>—</b><span>QQ 连接</span></div>
      <div class="stat"><b id="st-acct">—</b><span>机器人账号</span></div>
      <div class="stat"><b id="st-plug">—</b><span>已加载插件</span></div>
      <div class="stat"><b id="st-allow">—</b><span>白名单人数</span></div>
    </div>

    <div class="card">
      <div class="card-h">
        <div><h2>动作</h2><p>原来桌面面板上的按钮都在这里；服务在跑才可用。</p></div>
      </div>
      <div class="grid g4">
        <button class="btn ghost" onclick="act('/admin/login','扫码登录')">扫码登录</button>
        <button class="btn ghost" onclick="act('/admin/watchdog','掉线自愈')">开掉线自愈</button>
        <button class="btn ghost" onclick="act('/admin/restart','重启服务')">重启服务</button>
        <button class="btn ghost" onclick="act('/admin/backup','保存备份')">保存备份</button>
      </div>
      <pre class="out" id="actout" style="margin-top:14px">（扫码登录：弹出二维码窗口 · 掉线自愈：掉了自动重连 · 备份存到 安装目录/backups/）</pre>
    </div>

    <div class="card">
      <div class="card-h"><div><h2>白名单</h2><p>只有名单里的人，它才会回话。</p></div></div>
      <div class="block-title">私聊</div>
      <div class="chips" id="wl-users"><span class="chip">—</span></div>
      <div class="block-title">群</div>
      <div class="chips" id="wl-groups"><span class="chip">—</span></div>
    </div>

    <div class="card">
      <div class="card-h"><div><h2>最近用量</h2><p>今天调用了多少次模型。</p></div>
        <div class="right"><button class="btn ghost sm" onclick="loadUsage()">刷新</button></div>
      </div>
      <div class="chips" id="usage"><span class="chip">—</span></div>
    </div>
  </section>

  <!-- ============ 模型与人格 ============ -->
  <section class="tab" id="tab-llm">
    <div class="card">
      <div class="card-h">
        <div><h2>接口</h2><p>像不像真人主要看人格；这三项决定它能不能说话。</p></div>
        <div class="right"><button class="btn ghost sm" onclick="loadModels()">拉取可用模型</button></div>
      </div>
      <div class="grid g2">
        <label class="f"><span>接口地址 base_url</span>
          <input type="text" id="base_url" placeholder="https://api.deepseek.com/v1"></label>
        <label class="f"><span>API Key</span>
          <input type="password" id="api_key" placeholder="sk-…" autocomplete="off">
          <small><a href="javascript:void(0)" onclick="peekKey()">显示 / 隐藏</a></small></label>
      </div>
      <div class="grid g3" style="margin-top:14px">
        <label class="f"><span>模型名</span>
          <input type="text" id="model" list="models" placeholder="deepseek-chat">
          <datalist id="models"></datalist></label>
        <label class="f"><span>温度 <em id="tempv" style="color:var(--acc);font-style:normal">0.95</em></span>
          <input type="number" id="temperature" step="0.05" min="0" max="2" oninput="$('tempv').textContent=this.value"></label>
        <label class="f"><span>记忆轮数</span>
          <input type="number" id="history" min="0" max="30">
          <small>带多少条上下文，越大越贵</small></label>
      </div>
      <div class="chips" id="modelchips" style="margin-top:12px"></div>
    </div>

    <div class="card">
      <div class="card-h"><div><h2>人格</h2><p>她是谁、怎么说话、和你什么关系 —— 这一段最重要，写得越像真人越好。</p></div></div>
      <label class="f"><textarea id="persona" placeholder="你是…"></textarea></label>
    </div>

    <div class="card">
      <div class="card-h"><div><h2>开关</h2></div></div>
      <div class="grid g2">
        <label class="switch"><span>启用 AI 回复</span><input type="checkbox" id="llm_enabled"></label>
        <label class="switch"><span>模拟打字（打字机效果）</span><input type="checkbox" id="typing_enabled"></label>
      </div>
    </div>
  </section>

  <!-- ============ 行为 ============ -->
  <section class="tab" id="tab-beh">
    <div class="card">
      <div class="card-h"><div><h2>什么时候回</h2></div></div>
      <div class="grid g2">
        <label class="switch"><span>启用自动回复</span><input type="checkbox" id="enabled"></label>
        <label class="switch"><span>回私聊</span><input type="checkbox" id="reply_private"></label>
        <label class="switch"><span>回群聊</span><input type="checkbox" id="reply_group"></label>
        <label class="switch"><span>群里只回 @ 我</span><input type="checkbox" id="group_at_only"></label>
      </div>
      <div class="grid g2" style="margin-top:14px">
        <label class="f"><span>群回复概率（0–1）</span><input type="number" id="group_reply_probability" step="0.1" min="0" max="1"></label>
        <label class="f"><span>冷却（秒）</span><input type="number" id="cooldown" step="0.5" min="0"></label>
      </div>
    </div>

    <div class="card">
      <div class="card-h"><div><h2>怎么说</h2><p>像真人的关键：打字要慢一点、长句要拆成几条。</p></div></div>
      <div class="grid g2">
        <label class="switch"><span>长回复自动分段</span><input type="checkbox" id="split_enabled"></label>
        <label class="f"><span>最多分几条</span><input type="number" id="max_segments" min="1" max="6"></label>
        <label class="f"><span>每字延迟 ms</span><input type="number" id="per_char_ms" min="0"></label>
        <label class="f"><span>延迟上限 ms</span><input type="number" id="max_ms" min="0"></label>
      </div>
      <div class="grid" style="margin-top:14px">
        <label class="f"><span>兜底回复（AI 挂了时说）</span>
          <input type="text" id="fallback" placeholder="等我一下，刚在忙"></label>
      </div>
    </div>
  </section>

  <!-- ============ 记忆 ============ -->
  <section class="tab" id="tab-mem">
    <div class="card">
      <div class="card-h">
        <div><h2>它记得什么</h2><p>每个人格一个记忆库；点左边看具体聊过什么。</p></div>
        <div class="right">
          <button class="btn ghost sm" onclick="loadMemList()">刷新</button>
          <button class="btn danger sm" onclick="clearMem()">清空这段</button>
        </div>
      </div>
      <div class="mem">
        <div class="mem-list" id="memlist"><div class="hint" style="padding:8px">加载中…</div></div>
        <div class="mem-detail" id="memdetail"><div class="hint">← 左边选一个会话</div></div>
      </div>
    </div>
  </section>

  <!-- ============ 日志 ============ -->
  <section class="tab" id="tab-log">
    <div class="card">
      <div class="card-h">
        <div><h2>日志</h2><p>机器人不回话、掉线、报错，先看这里。</p></div>
        <div class="right">
          <label class="switch" style="padding:6px 10px"><span style="font-size:12px">隐藏噪声</span>
            <input type="checkbox" id="cleanlog" checked onchange="loadLogs()"></label>
          <label class="switch" style="padding:6px 10px"><span style="font-size:12px">自动刷新</span>
            <input type="checkbox" id="autolog" onchange="toggleAuto()"></label>
          <button class="btn ghost sm" onclick="loadLogs()">刷新</button>
        </div>
      </div>
      <div class="seg" style="margin-bottom:12px">
        <button class="active" data-log="qq-bridge">业务</button>
        <button data-log="nonebot">框架</button>
        <button data-log="watchdog">掉线自愈</button>
      </div>
      <pre class="log" id="logout">（读取中…）</pre>
    </div>
  </section>

  <!-- ============ 试聊 ============ -->
  <section class="tab" id="tab-chat">
    <div class="card">
      <div class="card-h"><div><h2>试聊</h2><p>用当前设置跑一遍，只给你看，不会发到 QQ。</p></div></div>
      <div class="grid" style="gap:10px">
        <label class="f"><span>说一句</span>
          <input type="text" id="testin" value="你是谁啊 怎么突然加我"
                 onkeydown="if(event.key==='Enter')testChat()"></label>
      </div>
      <div class="bubbles" id="testbub" style="margin-top:14px;max-height:none"></div>
      <div class="hint" id="testmeta" style="margin-top:10px">（还没测）</div>
      <div style="margin-top:14px"><button class="btn" onclick="testChat()">发送测试</button></div>
    </div>
  </section>
</div>

<div class="savebar" id="savebar">
  <div class="inner">
    <span class="status" id="savest">有改动没保存</span>
    <span class="spacer" style="flex:1"></span>
    <button class="btn ghost" onclick="reloadConfig()">撤销</button>
    <button class="btn" onclick="save()">保存并生效</button>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
const TOKEN = new URLSearchParams(location.search).get('token') || '';
const A = (u) => u + (TOKEN ? (u.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(TOKEN) : '');
const $ = id => document.getElementById(id);
const toast = (m, err) => {
  const t = $('toast'); t.textContent = m; t.className = 'toast show' + (err ? ' err' : '');
  clearTimeout(t._h); t._h = setTimeout(() => t.className = 'toast' + (err ? ' err' : ''), 2200);
};
let CFG = {}, MEMSEL = null, logFile = 'qq-bridge', autoTimer = null, DIRTY = false;

/* ---------- 标签页 ---------- */
document.querySelectorAll('nav.tabs button').forEach(b => b.onclick = () => {
  document.querySelectorAll('nav.tabs button').forEach(x => x.classList.toggle('active', x === b));
  document.querySelectorAll('section.tab').forEach(s => s.classList.toggle('active', s.id === 'tab-' + b.dataset.tab));
  updateSavebar();
  if (b.dataset.tab === 'mem') loadMemList();
  if (b.dataset.tab === 'log') loadLogs();
  window.scrollTo({top: 0, behavior: 'smooth'});
});

/* ---------- 读配置 ---------- */
async function reloadConfig() {
  const r = await fetch(A('/admin/config')); CFG = await r.json();
  const a = CFG.autoreply || {}, llm = a.llm || {}, ty = a.typing || {}, sp = a.split || {};
  $('enabled').checked = !!a.enabled;
  $('cooldown').value = a.cooldown ?? 2;
  $('reply_private').checked = !!a.reply_private;
  $('reply_group').checked = !!a.reply_group;
  $('group_at_only').checked = !!a.group_at_only;
  $('group_reply_probability').value = a.group_reply_probability ?? 1;
  $('fallback').value = a.fallback || '';
  $('typing_enabled').checked = !!ty.enabled;
  $('per_char_ms').value = ty.per_char_ms ?? 55;
  $('max_ms').value = ty.max_ms ?? 5000;
  $('split_enabled').checked = !!sp.enabled;
  $('max_segments').value = sp.max_segments ?? 3;
  $('llm_enabled').checked = !!llm.enabled;
  $('base_url').value = llm.base_url || '';
  $('api_key').value = llm.api_key || '';
  $('model').value = llm.model || '';
  $('temperature').value = llm.temperature ?? 0.95;
  $('tempv').textContent = llm.temperature ?? 0.95;
  $('history').value = llm.history ?? 10;
  $('persona').value = llm.persona || '';
  // 白名单展示（在 autoreply.whitelist 里）
  const allow = a.whitelist || CFG.allow || {};
  const users = allow.users || [], groups = allow.groups || [];
  $('wl-users').innerHTML = users.length ? users.map(u => `<span class="chip">${u}</span>`).join('')
    : '<span class="chip">（空的 · 用 tools/claim.py --auto 认领，或改 config.yaml 的 autoreply.whitelist.users）</span>';
  $('wl-groups').innerHTML = groups.length ? groups.map(g => `<span class="chip">${g}</span>`).join('')
    : '<span class="chip">（没有群）</span>';
  $('st-allow').textContent = users.length;
  document.querySelectorAll('#tab-llm input,#tab-beh input,#tab-llm textarea').forEach(el => el.oninput = markDirty);
  DIRTY = false;
  $('savest').textContent = '（没有改动）';
  updateSavebar();
}

/* ---------- 状态 ---------- */
async function loadStatus() {
  try {
    const st = await (await fetch(A('/status'))).json();
    const p = $('pill-conn');
    p.className = 'pill ' + (st.connected ? 'on' : 'off');
    $('pill-txt').textContent = st.connected ? '已连接 QQ' : '未连接';
    $('pill-acct').textContent = '账号 ' + (st.self_id || '—');
    $('st-conn').className = 'stat ' + (st.connected ? 'ok' : 'bad');
    $('st-conn').querySelector('b').textContent = st.connected ? '正常' : '断开';
    $('st-acct').textContent = st.self_id || '—';
    $('st-plug').textContent = st.plugins ?? '—';
  } catch (e) { /* 服务正在重启 */ }
}

/* ---------- 保存 ---------- */
function collect() {
  const a = JSON.parse(JSON.stringify(CFG.autoreply || {}));
  a.enabled = $('enabled').checked; a.cooldown = +$('cooldown').value;
  a.reply_private = $('reply_private').checked; a.reply_group = $('reply_group').checked;
  a.group_at_only = $('group_at_only').checked; a.group_reply_probability = +$('group_reply_probability').value;
  a.fallback = $('fallback').value;
  a.typing = Object.assign({}, a.typing, {enabled: $('typing_enabled').checked, per_char_ms: +$('per_char_ms').value, max_ms: +$('max_ms').value});
  a.split = Object.assign({}, a.split, {enabled: $('split_enabled').checked, max_segments: +$('max_segments').value});
  a.llm = Object.assign({}, a.llm, {
    enabled: $('llm_enabled').checked, base_url: $('base_url').value.trim(), api_key: $('api_key').value.trim(),
    model: $('model').value.trim(), temperature: +$('temperature').value, history: +$('history').value,
    persona: $('persona').value
  });
  return a;
}
function markDirty() { DIRTY = true; $('savest').textContent = '有改动没保存'; $('savebar').classList.add('show'); }
function updateSavebar() {
  const on = ['tab-llm', 'tab-beh'].includes(document.querySelector('section.tab.active')?.id);
  $('savebar').classList.toggle('show', on);
}
async function save() {
  $('savest').textContent = '保存中…';
  const r = await fetch(A('/admin/save'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({autoreply: collect()})});
  const d = await r.json();
  if (d.ok) { CFG.autoreply = collect(); DIRTY = false; $('savest').textContent = '已保存 ' + new Date().toLocaleTimeString(); toast('已保存，立即生效'); }
  else { $('savest').textContent = '保存失败'; toast('保存失败：' + (d.error || ''), true); }
}
document.addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); save(); } });

/* ---------- 模型 ---------- */
function peekKey() { const el = $('api_key'); el.type = el.type === 'password' ? 'text' : 'password'; }
async function loadModels() {
  toast('正在拉取模型列表…');
  const r = await fetch(A('/admin/models')); const d = await r.json();
  if (!d.ok) { toast('拉取失败：' + (d.error || ''), true); return; }
  const dl = $('models'); dl.innerHTML = '';
  d.models.forEach(m => { const o = document.createElement('option'); o.value = m; dl.appendChild(o); });
  $('modelchips').innerHTML = d.models.slice(0, 30)
    .map(m => `<span class="chip click" onclick="$('model').value='${m}';markDirty()">${m}</span>`).join('');
  toast('共 ' + d.models.length + ' 个模型，点一下就能填进去');
}

/* ---------- 试聊 ---------- */
async function testChat() {
  const text = $('testin').value.trim(); if (!text) return;
  $('testbub').innerHTML = `<div class="bub me">${esc(text)}</div><div class="bub her" id="waiting">正在想…</div>`;
  const r = await fetch(A('/admin/test'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text, autoreply: collect()})});
  const d = await r.json();
  if (d.ok) {
    $('testbub').innerHTML = `<div class="bub me">${esc(text)}</div><div class="bub her">${esc(d.reply || '(空回复)')}</div>`;
    $('testmeta').textContent = `${d.model} · ${d.ms}ms` + (d.reasoning ? ' · 带思考' : '');
  } else {
    $('testbub').innerHTML = `<div class="bub me">${esc(text)}</div><div class="bub her">（出错）</div>`;
    $('testmeta').textContent = '出错：' + (d.error || '');
  }
}
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c])); }

/* ---------- 动作 ---------- */
async function act(path, label) {
  $('actout').textContent = label + '…';
  try {
    const r = await fetch(A(path), {method: 'POST'});
    const d = await r.json();
    let t = d.hint || (d.ok ? '已完成' : '失败');
    if (d.path) t += `\n存到：${d.path}\n大小 ${d.size_mb} MB · 记忆库 ${d.db} · 对话文件 ${d.chat_files} · 日志 ${d.logs}`;
    if (d.error) t += '\n' + d.error;
    $('actout').textContent = t;
    toast(label + (d.ok ? ' ✓' : ' ✗'), !d.ok);
  } catch (e) {
    $('actout').textContent = label + '：服务在重启，等 10 秒刷新本页';
    toast(label + ' 已发出');
  }
}

/* ---------- 记忆 ---------- */
async function loadMemList() {
  $('memlist').innerHTML = '<div class="hint" style="padding:8px">加载中…</div>';
  const d = await (await fetch(A('/admin/memory'))).json();
  if (!d.ok) { $('memlist').innerHTML = '<div class="hint" style="padding:8px">读取失败：' + esc(d.error || '') + '</div>'; return; }
  if (!d.chats.length) { $('memlist').innerHTML = '<div class="hint" style="padding:8px">还没有会话记录</div>'; return; }
  $('memlist').innerHTML = d.chats.map((c, i) =>
    `<div class="mem-item${i === 0 ? ' active' : ''}" data-i="${i}">
       <span>${esc(c.chat)}</span><i>${c.count}${c.persona ? ' · ' + esc(c.persona) : ''}</i>
     </div>`).join('');
  document.querySelectorAll('.mem-item').forEach(el => el.onclick = () => {
    document.querySelectorAll('.mem-item').forEach(x => x.classList.toggle('active', x === el));
    showMem(d.chats[+el.dataset.i]);
  });
  MEMSEL = d.chats[0];
  showMem(d.chats[0]);
}
async function showMem(c) {
  if (!c) return;
  MEMSEL = c;
  $('memdetail').innerHTML = '<div class="hint">读取中…</div>';
  const q = `/admin/memory?persona=${encodeURIComponent(c.persona || '')}&chat=${encodeURIComponent(c.chat)}`;
  const d = await (await fetch(A(q))).json();
  if (!d.ok) { $('memdetail').innerHTML = '<div class="hint">读取失败：' + esc(d.error || '') + '</div>'; return; }
  const facts = Object.entries(d.facts || {});
  const bubs = (d.recent || []).map(m =>
    `<div class="bub ${m.role === 'user' ? 'me' : 'her'}">${esc(m.content || '')}</div>`).join('');
  $('memdetail').innerHTML = `
    <div class="hint">${esc(d.chat)} · ${d.count} 条消息${c.persona ? ' · 人格 ' + esc(c.persona) : ''}</div>
    ${d.summary ? `<div class="block-title">阶段性总结</div><div class="out">${esc(d.summary)}</div>` : ''}
    <div class="block-title">记住的事</div>
    <div class="chips">${facts.length ? facts.map(([k, v]) => `<span class="chip">${esc(k)}：${esc(v)}</span>`).join('') : '<span class="chip">（还没记住什么）</span>'}</div>
    <div class="block-title">最近对话</div>
    <div class="bubbles">${bubs || '<div class="hint">（没有记录）</div>'}</div>`;
}
async function clearMem() {
  if (!MEMSEL) return toast('先选一个会话', true);
  if (!confirm(`确定清空 ${MEMSEL.chat} 的记忆？清完就完全不记得你们聊过什么了`)) return;
  const r = await fetch(A('/admin/memory/clear'), {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({persona: MEMSEL.persona, chat: MEMSEL.chat})});
  const d = await r.json();
  toast(d.ok ? '已清空' : '失败：' + (d.error || ''), !d.ok);
  loadMemList();
}

/* ---------- 日志 ---------- */
document.querySelectorAll('.seg button').forEach(b => b.onclick = () => {
  document.querySelectorAll('.seg button').forEach(x => x.classList.toggle('active', x === b));
  logFile = b.dataset.log; loadLogs();
});
async function loadLogs() {
  const clean = $('cleanlog').checked ? 1 : 0;
  const d = await (await fetch(A('/admin/logs?file=' + logFile + '&n=300&clean=' + clean))).json();
  const pre = $('logout');
  pre.textContent = d.ok ? (d.lines || '（空）') : '读取失败：' + (d.error || '');
  pre.scrollTop = pre.scrollHeight;
}
function toggleAuto() {
  clearInterval(autoTimer);
  if ($('autolog').checked) autoTimer = setInterval(() => { if (document.querySelector('#tab-log').classList.contains('active')) loadLogs(); }, 5000);
}

/* ---------- 用量 ---------- */
async function loadUsage() {
  try {
    const d = await (await fetch(A('/admin/usage?days=1'))).json();
    if (!d.ok) { $('usage').innerHTML = '<span class="chip">读取失败</span>'; return; }
    const NAME = {days: '统计天数', calls: '调用次数', tokens: '总 tokens', prompt_tokens: '输入 tokens',
                  completion_tokens: '输出 tokens', cost: '估算花费', requests: '请求数'};
    const items = Object.entries(d)
      .filter(([k, v]) => k !== 'ok' && (typeof v === 'number' || typeof v === 'string'))
      .filter(([k]) => k in NAME);
    $('usage').innerHTML = items.length
      ? items.map(([k, v]) => `<span class="chip">${NAME[k]}：${esc(v)}</span>`).join('')
      : '<span class="chip">今天还没用过</span>';
  } catch (e) { $('usage').innerHTML = '<span class="chip">读取失败</span>'; }
}

/* ---------- 启动 ---------- */
reloadConfig().then(() => { loadStatus(); loadUsage(); });
setInterval(loadStatus, 8000);
</script>
</body>
</html>
"""
