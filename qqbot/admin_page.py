"""网页配置台的页面（唯一后台的 UI）。

单独放一个文件，方便改样式；由 admin.py 导入 PAGE 给 http_api 用。
纯原生 HTML/CSS/JS，不依赖任何 CDN —— 客户机器上断网也能打开。

布局：左边固定导航，右边内容区（浅色 + 薄荷绿点缀）。
"""

PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>qq-bridge 控制台</title>
<style>
  :root{
    --bg:#f4f7f6; --surface:#ffffff; --surface-2:#f7faf9; --surface-3:#eef4f2;
    --line:#e4ecea; --line-2:#d3e0dd;
    --fg:#12211d; --dim:#5d716c; --dim-2:#8b9d98;
    --acc:#10b981; --acc-2:#34d399; --acc-ink:#0b7f5f; --acc-bg:#e6f7f0;
    --ok:#0f9d6e; --warn:#d98314; --danger:#e04b4b;
    --shadow:0 1px 2px rgba(16,40,35,.05), 0 12px 28px -18px rgba(16,40,35,.28);
    --r:16px; --r-sm:10px; --side:250px;
  }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0}
  body{
    background:var(--bg);
    color:var(--fg);
    font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
    -webkit-font-smoothing:antialiased;
  }
  a{color:var(--acc-ink);text-decoration:none}
  a:hover{text-decoration:underline}

  /* ---------- 外壳：左导航 + 右内容 ---------- */
  .app{display:flex;min-height:100vh}

  aside.side{
    width:var(--side);flex:0 0 var(--side);
    position:sticky;top:0;height:100vh;
    display:flex;flex-direction:column;gap:6px;
    padding:18px 14px;
    background:var(--surface);
    border-right:1px solid var(--line);
  }
  .brand{display:flex;align-items:center;gap:10px;padding:6px 8px 16px}
  .logo{
    width:34px;height:34px;border-radius:11px;flex:0 0 34px;
    background:linear-gradient(135deg,var(--acc),#0ea5a4);
    display:grid;place-items:center;color:#fff;font-size:16px;font-weight:800;
    box-shadow:0 8px 18px -8px rgba(16,185,129,.7);
  }
  .brand b{display:block;font-size:15px;font-weight:750;letter-spacing:.2px;line-height:1.25}
  .brand small{display:block;color:var(--dim-2);font-size:11.5px;font-weight:500}

  nav.nav{display:flex;flex-direction:column;gap:2px}
  nav.nav button{
    display:flex;align-items:center;gap:11px;width:100%;
    border:0;background:transparent;color:var(--dim);
    font:600 13.5px/1 inherit;padding:11px 12px;border-radius:12px;cursor:pointer;
    transition:.15s;text-align:left;
  }
  nav.nav button svg{width:18px;height:18px;flex:0 0 18px;stroke:currentColor;fill:none;
    stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round;opacity:.85}
  nav.nav button:hover{background:var(--surface-3);color:var(--fg)}
  nav.nav button.active{background:var(--acc-bg);color:var(--acc-ink)}
  nav.nav button.active svg{opacity:1}

  .side-foot{margin-top:auto;padding:12px;border-radius:14px;background:var(--surface-2);
    border:1px solid var(--line)}
  .side-foot .t{font-size:12px;font-weight:700;color:var(--fg);margin-bottom:4px}
  .side-foot .d{font-size:11.5px;color:var(--dim-2);line-height:1.55}

  main.main{flex:1;min-width:0;display:flex;flex-direction:column}

  .topbar{
    position:sticky;top:0;z-index:30;
    display:flex;align-items:center;gap:14px;flex-wrap:wrap;
    padding:16px 26px;background:rgba(244,247,246,.86);
    border-bottom:1px solid var(--line);backdrop-filter:blur(12px);
  }
  .tb-l h1{margin:0;font-size:19px;font-weight:750;letter-spacing:.2px}
  .tb-l p{margin:2px 0 0;font-size:12.5px;color:var(--dim)}
  .tb-r{margin-left:auto;display:flex;align-items:center;gap:8px;flex-wrap:wrap}

  .content{padding:22px 26px 120px;max-width:1080px;width:100%}

  /* ---------- 状态胶囊 ---------- */
  .pill{
    display:inline-flex;align-items:center;gap:7px;
    padding:6px 11px;border-radius:999px;font-size:12px;font-weight:650;
    background:var(--surface);border:1px solid var(--line);color:var(--dim);
    white-space:nowrap;
  }
  .pill .dot{width:7px;height:7px;border-radius:50%;background:var(--dim-2)}
  .pill.on{color:var(--ok);border-color:rgba(16,185,129,.32);background:var(--acc-bg)}
  .pill.on .dot{background:var(--ok);box-shadow:0 0 0 3px rgba(16,185,129,.16)}
  .pill.off{color:var(--danger);border-color:rgba(224,75,75,.28);background:#fdecec}
  .pill.off .dot{background:var(--danger)}
  .spacer{flex:1}

  section.tab{display:none;animation:fade .18s ease}
  section.tab.active{display:block}
  @keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}

  /* ---------- 卡片 ---------- */
  .card{
    background:var(--surface);border:1px solid var(--line);border-radius:var(--r);
    padding:20px 22px;margin-bottom:16px;box-shadow:var(--shadow);
  }
  .card-h{display:flex;align-items:flex-start;gap:12px;margin-bottom:16px}
  .card-h h2{margin:0;font-size:15px;font-weight:720;letter-spacing:.2px}
  .card-h p{margin:4px 0 0;font-size:12.5px;color:var(--dim);line-height:1.55}
  .card-h .right{margin-left:auto;display:flex;gap:8px;align-items:center}

  /* ---------- 表单 ---------- */
  .grid{display:grid;gap:14px}
  .g2{grid-template-columns:repeat(2,minmax(0,1fr))}
  .g3{grid-template-columns:repeat(3,minmax(0,1fr))}
  .g4{grid-template-columns:repeat(4,minmax(0,1fr))}
  @media (max-width:860px){.g3,.g4{grid-template-columns:repeat(2,minmax(0,1fr))}}
  @media (max-width:520px){.g2,.g3,.g4{grid-template-columns:1fr}}
  label.f{display:block}
  label.f > span{display:block;font-size:12px;color:var(--dim);margin:0 0 6px;font-weight:650}
  label.f small{display:block;color:var(--dim-2);font-size:11.5px;font-weight:400;margin-top:6px}
  input[type=text],input[type=password],input[type=number],textarea,select{
    width:100%;padding:10px 12px;background:var(--surface);color:var(--fg);
    border:1px solid var(--line-2);border-radius:var(--r-sm);
    font:13.5px/1.55 inherit;outline:none;transition:.15s;
  }
  input:hover,textarea:hover,select:hover{border-color:#b9cdc8}
  input:focus,textarea:focus,select:focus{
    border-color:var(--acc);box-shadow:0 0 0 3px rgba(16,185,129,.15);background:#fff;
  }
  textarea{min-height:190px;resize:vertical;line-height:1.75}
  .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px}

  /* 开关 */
  .switch{display:flex;align-items:center;justify-content:space-between;gap:12px;
    padding:11px 13px;background:var(--surface-2);border:1px solid var(--line);border-radius:var(--r-sm);
    cursor:pointer;transition:.15s;user-select:none}
  .switch:hover{border-color:var(--line-2);background:#f3f8f6}
  .switch span{font-size:13px;font-weight:650;color:var(--fg)}
  .switch input{appearance:none;width:38px;height:22px;border-radius:999px;background:#cfdcda;
    position:relative;cursor:pointer;transition:.18s;flex:0 0 38px;margin:0;border:0}
  .switch input::after{content:"";position:absolute;top:3px;left:3px;width:16px;height:16px;
    border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.2);transition:.18s}
  .switch input:checked{background:var(--acc)}
  .switch input:checked::after{left:19px}

  /* 按钮 */
  button{font:650 13px/1 inherit;cursor:pointer;border-radius:var(--r-sm);transition:.15s}
  .btn{padding:10px 16px;border:1px solid transparent;color:#fff;
    background:linear-gradient(135deg,var(--acc),#0fa3a0);
    box-shadow:0 8px 18px -10px rgba(16,185,129,.9);display:inline-flex;align-items:center;gap:6px}
  .btn:hover{filter:brightness(1.05)}
  .btn:active{transform:translateY(1px)}
  .btn.ghost{background:var(--surface);border-color:var(--line-2);color:var(--fg);box-shadow:none}
  .btn.ghost:hover{background:var(--surface-2);border-color:#b9cdc8}
  .btn.danger{background:#fdecec;border-color:rgba(224,75,75,.3);color:#c23a3a;box-shadow:none}
  .btn.danger:hover{background:#fbdede}
  .btn:disabled{opacity:.5;cursor:not-allowed}
  .btn.sm{padding:8px 12px;font-size:12.5px}

  /* 统计块 */
  .stats{display:grid;gap:14px;grid-template-columns:repeat(4,minmax(0,1fr))}
  @media (max-width:860px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
  .stat{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:15px 16px;
    box-shadow:var(--shadow)}
  .stat b{display:block;font-size:22px;font-weight:750;letter-spacing:.2px;line-height:1.25}
  .stat span{display:block;font-size:11.5px;color:var(--dim);margin-top:5px;font-weight:600}
  .stat.ok b{color:var(--ok)} .stat.bad b{color:var(--danger)}

  /* 服务在线监控 */
  .hlist{display:grid;gap:10px;grid-template-columns:repeat(2,minmax(0,1fr))}
  @media (max-width:860px){.hlist{grid-template-columns:1fr}}
  .hrow{display:flex;align-items:flex-start;gap:11px;padding:12px 14px;
    background:var(--surface-2);border:1px solid var(--line);border-radius:13px;transition:.15s}
  .hrow.ok{border-color:rgba(16,185,129,.28);background:#f2fbf7}
  .hrow.bad{border-color:rgba(224,75,75,.3);background:#fdf3f3}
  .hdot{width:9px;height:9px;border-radius:50%;flex:0 0 9px;margin-top:6px;background:#c2d1cd}
  .hrow.ok .hdot{background:var(--ok);box-shadow:0 0 0 4px rgba(16,185,129,.15)}
  .hrow.bad .hdot{background:var(--danger);box-shadow:0 0 0 4px rgba(224,75,75,.14)}
  .hmain{min-width:0;flex:1}
  .hmain b{display:block;font-size:13px;font-weight:700;line-height:1.35}
  .hmain span{display:block;font-size:11.5px;color:var(--dim);margin-top:2px;
    overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .hrow em{font-style:normal;font-size:11.5px;font-weight:750;flex:0 0 auto;margin-top:2px;
    color:var(--ok)}
  .hrow.bad em{color:var(--danger)}
  .hrow .tip{display:none}

  /* 记忆 */
  .mem{display:grid;grid-template-columns:240px minmax(0,1fr);gap:14px}
  @media (max-width:860px){.mem{grid-template-columns:1fr}}
  .mem-list{background:var(--surface-2);border:1px solid var(--line);border-radius:14px;padding:6px;
    max-height:520px;overflow:auto}
  .mem-item{padding:9px 11px;border-radius:10px;cursor:pointer;font-size:12.5px;color:var(--dim);
    display:flex;justify-content:space-between;gap:8px;transition:.13s}
  .mem-item:hover{background:#fff;color:var(--fg)}
  .mem-item.active{background:var(--acc-bg);color:var(--acc-ink);font-weight:650}
  .mem-item i{font-style:normal;color:var(--dim-2);font-size:11px}
  .mem-detail{min-width:0}
  .chips{display:flex;flex-wrap:wrap;gap:7px;margin:2px 0 0}
  .chip{font-size:12px;padding:5px 10px;border-radius:999px;background:var(--surface-2);
    border:1px solid var(--line);color:var(--dim)}
  .chip.click{cursor:pointer}
  .chip.click:hover{border-color:var(--acc);color:var(--acc-ink);background:var(--acc-bg)}
  .bubbles{display:flex;flex-direction:column;gap:8px;max-height:340px;overflow:auto;padding:4px 2px}
  .bub{max-width:82%;padding:9px 13px;border-radius:14px;font-size:13px;line-height:1.6;
    white-space:pre-wrap;word-break:break-word}
  .bub.me{align-self:flex-end;background:linear-gradient(135deg,var(--acc),#0fa3a0);color:#fff;
    border-bottom-right-radius:5px}
  .bub.her{align-self:flex-start;background:var(--surface-2);border:1px solid var(--line);
    border-bottom-left-radius:5px}
  .block-title{font-size:11.5px;font-weight:750;color:var(--dim-2);letter-spacing:.8px;
    margin:16px 0 8px;text-transform:uppercase}
  .block-title:first-child{margin-top:0}

  /* 日志 */
  .seg{display:inline-flex;gap:3px;padding:3px;background:var(--surface-2);
    border:1px solid var(--line);border-radius:11px}
  .seg button{border:0;background:transparent;color:var(--dim);padding:8px 13px;border-radius:8px;
    font-size:12.5px;font-weight:650}
  .seg button.active{background:var(--surface);color:var(--acc-ink);box-shadow:var(--shadow)}
  pre.log{margin:0;background:#0f1a18;border:1px solid #16241f;border-radius:12px;padding:14px;
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;line-height:1.65;
    color:#b8cfc7;max-height:58vh;overflow:auto;white-space:pre-wrap;word-break:break-all}
  pre.log::-webkit-scrollbar,.bubbles::-webkit-scrollbar,.mem-list::-webkit-scrollbar,
  .out::-webkit-scrollbar{width:9px;height:9px}
  pre.log::-webkit-scrollbar-thumb,.bubbles::-webkit-scrollbar-thumb,
  .mem-list::-webkit-scrollbar-thumb,.out::-webkit-scrollbar-thumb{
    background:#c3d3ce;border-radius:9px}
  .hint{font-size:12px;color:var(--dim-2);line-height:1.6}
  .plug{display:flex;gap:14px;align-items:flex-start;padding:14px 0;border-top:1px solid var(--line)}
  .plug:first-child{border-top:0;padding-top:0}
  .plug-main{min-width:0;flex:1}
  .plug-h{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px}
  .plug-h b{font-size:13.5px}
  .plug-h code{font-size:11px;color:var(--dim);background:var(--surface-2);
    border:1px solid var(--line);padding:2px 6px;border-radius:6px}
  .plug .chips{margin-top:8px}
  .chip.warn{color:var(--warn);border-color:rgba(217,131,20,.3);background:#fdf4e6}
  .plug .switch{flex:0 0 auto;min-width:86px}
  .sec-title{font-size:13px;font-weight:720;color:var(--fg);letter-spacing:.3px;margin:2px 0 10px;
    padding-bottom:8px;border-bottom:1px solid var(--line)}
  .sec-sub{font-size:11.5px;font-weight:750;color:var(--dim-2);letter-spacing:1px;margin:16px 0 4px}
  .out{margin:0;background:var(--surface-2);border:1px solid var(--line);border-radius:12px;padding:13px;
    font:12.5px/1.7 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--fg);
    white-space:pre-wrap;word-break:break-word;max-height:300px;overflow:auto}

  /* 底部保存条 */
  .savebar{
    position:fixed;left:0;right:0;bottom:0;z-index:40;display:none;gap:12px;align-items:center;
    padding:12px 26px;background:rgba(255,255,255,.92);border-top:1px solid var(--line);
    backdrop-filter:blur(14px);box-shadow:0 -8px 24px -18px rgba(16,40,35,.4);
  }
  .savebar.show{display:flex}
  .savebar .inner{max-width:1080px;margin:0 auto;display:flex;gap:12px;align-items:center;width:100%}
  .savebar .status{font-size:12.5px;color:var(--dim);font-weight:600}

  .toast{
    position:fixed;right:22px;bottom:76px;z-index:60;
    padding:11px 16px;border-radius:12px;font-size:13px;font-weight:650;
    background:#0f1a18;color:#e8f5f0;
    opacity:0;transform:translateY(8px);transition:.22s;pointer-events:none;
    box-shadow:0 12px 30px -12px rgba(9,30,25,.6);max-width:min(90vw,420px);
  }
  .toast.show{opacity:1;transform:none}
  .toast.err{background:#8f2323;color:#ffe9e9}

  /* 窄屏：导航挪到顶部 */
  @media (max-width:900px){
    .app{display:block}
    aside.side{position:static;width:auto;height:auto;flex-direction:column;gap:0;
      padding:12px 14px 10px;border-right:0;border-bottom:1px solid var(--line)}
    .brand{padding:2px 4px 10px}
    nav.nav{flex-direction:row;overflow-x:auto;gap:6px;padding-bottom:4px;scrollbar-width:none}
    nav.nav::-webkit-scrollbar{display:none}
    nav.nav button{width:auto;white-space:nowrap;padding:9px 12px}
    .side-foot{display:none}
    .topbar{padding:12px 16px}
    .content{padding:16px 16px 120px}
    .savebar{padding:12px 16px}
  }
</style>
</head>
<body>
<div class="app">

  <aside class="side">
    <div class="brand">
      <div class="logo">Q</div>
      <div><b>qq-bridge</b><small>机器人控制台</small></div>
    </div>

    <nav class="nav">
      <button class="active" data-tab="ov">
        <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></svg>
        概览
      </button>
      <button data-tab="llm">
        <svg viewBox="0 0 24 24"><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/><circle cx="12" cy="12" r="3.2"/></svg>
        模型
      </button>
      <button data-tab="persona">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="3.6"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/></svg>
        人格
      </button>
      <button data-tab="plug">
        <svg viewBox="0 0 24 24"><path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2.2"/><circle cx="10" cy="17" r="2.2"/></svg>
        功能
      </button>
      <button data-tab="mem">
        <svg viewBox="0 0 24 24"><ellipse cx="12" cy="6" rx="7.5" ry="3"/><path d="M4.5 6v6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3V6"/><path d="M4.5 12v6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-6"/></svg>
        记忆
      </button>
      <button data-tab="log">
        <svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/></svg>
        日志
      </button>
    </nav>

    <div class="side-foot">
      <div class="t">Ctrl + S 保存</div>
      <div class="d">配置改动后点右下角「保存并生效」，不用重启。</div>
    </div>
  </aside>

  <main class="main">

    <div class="topbar">
      <div class="tb-l">
        <h1 id="page-title">概览</h1>
        <p id="page-sub">机器人状态、登录、白名单一眼看完</p>
      </div>
      <div class="tb-r">
        <span class="pill" id="pill-conn"><span class="dot"></span><span id="pill-txt">连接中…</span></span>
        <span class="pill" id="pill-acct">账号 —</span>
        <a class="btn ghost sm" id="napcat-link" href="http://127.0.0.1:6099" target="_blank" rel="noreferrer">NapCat 面板</a>
        <button class="btn ghost sm" onclick="act('/admin/login','扫码登录')">扫码登录</button>
        <button class="btn ghost sm" onclick="act('/admin/restart','重启服务')">重启</button>
      </div>
    </div>

    <div class="content">

  <!-- ============ 概览 ============ -->
  <section class="tab active" id="tab-ov">
    <div class="card" id="needlogin" style="display:none;border-color:rgba(224,75,75,.32);background:#fdf1f1">
      <div class="card-h">
        <div>
          <h2 style="color:#c23a3a">还没登录 QQ</h2>
          <p>用手机 QQ 扫下面这张码；扫完这一页自己会变绿，不用刷新。</p>
        </div>
      </div>
      <div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap">
        <img id="loginqr" alt="登录二维码" style="width:186px;height:186px;object-fit:contain;background:#fff;border-radius:12px;padding:8px;border:1px solid var(--line)">
        <div style="display:flex;flex-direction:column;gap:10px;min-width:180px">
          <button class="btn ghost" onclick="refreshQR(this)">换一张二维码</button>
          <span id="loginstat" style="font-size:13px;color:var(--dim)">等待扫码…</span>
        </div>
      </div>
    </div>

    <div class="stats" style="margin-bottom:16px">
      <div class="stat" id="st-conn"><b>—</b><span>QQ 连接</span></div>
      <div class="stat"><b id="st-acct">—</b><span>机器人账号</span></div>
      <div class="stat"><b id="st-plug">—</b><span>已加载功能</span></div>
      <div class="stat"><b id="st-allow">—</b><span>白名单人数</span></div>
    </div>

    <div class="card">
      <div class="card-h">
        <div><h2>服务在线</h2><p>每个服务单独探活，8 秒自动刷新一次；红了先看提示那一列。</p></div>
        <div class="right">
          <span class="chip" id="health-sum">—</span>
          <button class="btn ghost sm" onclick="loadHealth()">刷新</button>
        </div>
      </div>
      <div class="hlist" id="health"><div class="hint">读取中…</div></div>
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
      <div class="card-h">
        <div><h2>NapCat 面板</h2>
          <p>扫码登录、看 QQ 在不在线、改连接配置都在这里。手机 QQ 扫面板里的二维码即可。</p></div>
        <div class="right"><a class="btn ghost sm" id="napcat-open" href="http://127.0.0.1:6099"
             target="_blank" rel="noreferrer">打开面板</a></div>
      </div>
      <div class="grid g2">
        <label class="f"><span>面板地址</span>
          <input type="text" id="napcat-url" readonly onclick="this.select()"></label>
        <label class="f"><span>面板密码（token）</span>
          <div style="display:flex;gap:8px">
            <input type="text" id="napcat-token" readonly onclick="this.select()" style="flex:1">
            <button class="btn ghost sm" onclick="copyNapcat()">复制</button>
          </div>
          <small>打开面板时如果提示登录，把这个密码填进去</small></label>
      </div>
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

  <!-- ============ 模型 ============ -->
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
        <label class="f"><span>温度 <em id="tempv" style="color:var(--acc-ink);font-style:normal">0.95</em></span>
          <input type="number" id="temperature" step="0.05" min="0" max="2" oninput="$('tempv').textContent=this.value"></label>
        <label class="f"><span>记忆轮数</span>
          <input type="number" id="history" min="0" max="30">
          <small>带多少条上下文，越大越贵</small></label>
      </div>
      <div class="chips" id="modelchips" style="margin-top:12px"></div>
    </div>

    <div class="card">
      <div class="card-h"><div><h2>回复开关</h2><p>关掉 AI 回复，她就只当哑巴（指令插件还能用）。</p></div></div>
      <div class="grid g2">
        <label class="switch"><span>启用 AI 回复</span><input type="checkbox" id="llm_enabled"></label>
        <label class="switch"><span>模拟打字（打字机效果）</span><input type="checkbox" id="typing_enabled"></label>
      </div>
    </div>
  </section>

  <!-- ============ 人格 ============ -->
  <section class="tab" id="tab-persona">
    <div class="card">
      <div class="card-h">
        <div><h2>人格</h2><p>她是谁、怎么说话、和你什么关系 —— 这一段最重要，写得越像真人越好。</p></div>
        <div class="right"><span class="chip" id="pcount">0 字</span></div>
      </div>
      <label class="f"><textarea id="persona" placeholder="你是…"
        oninput="document.getElementById('pcount').textContent=this.value.length+' 字'"></textarea></label>
      <div class="hint" style="margin-top:10px">
        只改这段文字 = 改「当前人格」的说法。一个 QQ 号固定一个人格，第一次聊天时自动绑定，之后不能换；
        QQ 里发 <b>人格</b> 可以看她是谁，<b>记忆</b> 看她记得你什么，<b>忘记我</b> 清空当前会话。
      </div>
    </div>
  </section>

  <!-- ============ 功能 ============ -->
  <section class="tab" id="tab-plug">
    <div class="card">
      <div class="card-h">
        <div><h2>功能</h2>
          <p>上面是她身上的功能（心情 / 好感度 / 表情包 / 语音 …），下面是指令插件（ping / 截屏 …）。
             拨一下立即生效，不用重启。</p></div>
        <div class="right"><button class="btn ghost sm" onclick="loadPlugins()">刷新</button></div>
      </div>
      <div id="pluglist"><div class="hint">读取中…</div></div>
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

    </div>
  </main>
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

/* 每个页签的标题和副标题（顶栏跟着变） */
const PAGES = {
  ov:      ['概览', '机器人状态、登录、白名单一眼看完'],
  llm:     ['模型', '接口地址、密钥、模型名'],
  persona: ['人格', '她是谁、怎么说话'],
  plug:    ['功能', '她身上的能力和指令插件，逐个开关'],
  mem:     ['记忆', '她记得的事，和最近聊过什么'],
  log:     ['日志', '不回话、掉线、报错先看这里']
};

/* ---------- 页签 ---------- */
document.querySelectorAll('nav.nav button').forEach(b => b.onclick = () => {
  document.querySelectorAll('nav.nav button').forEach(x => x.classList.toggle('active', x === b));
  document.querySelectorAll('section.tab').forEach(s => s.classList.toggle('active', s.id === 'tab-' + b.dataset.tab));
  const meta = PAGES[b.dataset.tab] || ['', ''];
  if ($('page-title')) $('page-title').textContent = meta[0];
  if ($('page-sub')) $('page-sub').textContent = meta[1];
  updateSavebar();
  if (b.dataset.tab === 'mem') loadMemList();
  if (b.dataset.tab === 'log') loadLogs();
  if (b.dataset.tab === 'plug') loadPlugins();
  document.querySelector('.main').scrollTo({top: 0, behavior: 'smooth'});
  window.scrollTo({top: 0, behavior: 'smooth'});
});

/* ---------- 读配置 ---------- */
async function reloadConfig() {
  const r = await fetch(A('/admin/config')); CFG = await r.json();
  const a = CFG.autoreply || {}, llm = a.llm || {}, ty = a.typing || {}, sp = a.split || {};
  // 「行为」页已删：自动回复 / 分段 / 打字延迟这些项只在 config.yaml 里改，页面不再碰它们
  $('llm_enabled').checked = !!llm.enabled;
  $('base_url').value = llm.base_url || '';
  $('api_key').value = llm.api_key || '';
  $('model').value = llm.model || '';
  $('temperature').value = llm.temperature ?? 0.95;
  $('tempv').textContent = llm.temperature ?? 0.95;
  $('history').value = llm.history ?? 10;
  $('persona').value = llm.persona || '';
  $('pcount').textContent = ($('persona').value || '').length + ' 字';
  // 白名单展示（在 autoreply.whitelist 里）
  const allow = a.whitelist || CFG.allow || {};
  const users = allow.users || [], groups = allow.groups || [];
  $('wl-users').innerHTML = users.length ? users.map(u => `<span class="chip">${u}</span>`).join('')
    : '<span class="chip">（空的 · 用 tools/claim.py --auto 认领，或改 config.yaml 的 autoreply.whitelist.users）</span>';
  $('wl-groups').innerHTML = groups.length ? groups.map(g => `<span class="chip">${g}</span>`).join('')
    : '<span class="chip">（没有群）</span>';
  $('st-allow').textContent = users.length;
  document.querySelectorAll('#tab-llm input,#tab-persona textarea').forEach(el => el.oninput = markDirty);
  DIRTY = false;
  $('savest').textContent = '（没有改动）';
  updateSavebar();
}

/* ---------- NapCat 面板信息 ---------- */
async function loadNapcat() {
  try {
    const d = await (await fetch(A('/admin/napcat'))).json();
    if (!d.ok) return;
    $('napcat-url').value = d.url;
    $('napcat-token').value = d.token || '（没设密码）';
    $('napcat-open').href = d.webui || d.url;
    $('napcat-link').href = d.webui || d.url;
  } catch (e) { /* 忽略 */ }
}
function copyNapcat() {
  const v = $('napcat-token').value;
  navigator.clipboard?.writeText(v).then(() => toast('密码已复制'), () => {
    $('napcat-token').select(); document.execCommand('copy'); toast('密码已复制');
  });
}

/* ---------- 服务在线监控 ---------- */
async function loadHealth() {
  const box = $('health');
  if (!box) return;
  try {
    const d = await (await fetch(A('/admin/health'))).json();
    if (!d.ok) { box.innerHTML = '<div class="hint">读取失败</div>'; return; }
    box.innerHTML = d.items.map(it => `
      <div class="hrow ${it.ok ? 'ok' : 'bad'}" title="${esc(it.tip || '')}">
        <span class="hdot"></span>
        <div class="hmain">
          <b>${esc(it.name)}</b>
          <span>${esc(it.ok ? (it.detail || '在线') : (it.detail || '异常') + ' · ' + (it.tip || ''))}</span>
        </div>
        <em>${it.ok ? '在线' : '异常'}</em>
      </div>`).join('');
    const sum = $('health-sum');
    if (sum) {
      sum.textContent = d.online + ' / ' + d.total + ' 在线';
      sum.className = 'chip' + (d.online === d.total ? '' : ' warn');
    }
  } catch (e) {
    box.innerHTML = '<div class="hint">读取失败（服务在重启？）</div>';
  }
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
    $('needlogin').style.display = st.connected ? 'none' : 'block';
    // 没登录就在这一页直接显示二维码，省得再开一个页面
    if (!st.connected) {
      const q = $('loginqr');
      if (q && Date.now() - (window.__qrAt || 0) > 4000) {
        q.src = A('/admin/qr.png') + '&t=' + Date.now();
        window.__qrAt = Date.now();
      }
      if ($('loginstat')) $('loginstat').textContent = '等待扫码…';
    } else if ($('loginstat')) {
      $('loginstat').textContent = '已登录 QQ ' + (st.self_id || '');
    }
  } catch (e) { /* 服务正在重启 */ }
}

async function refreshQR(btn) {
  const old = btn.textContent;
  btn.disabled = true; btn.textContent = '刷新中…';
  if ($('loginstat')) $('loginstat').textContent = '正在重开协议端，约 20 秒出新码…';
  try { await fetch(A('/admin/qr/refresh'), {method: 'POST'}); } catch (e) {}
  window.__qrAt = 0;
  setTimeout(() => { btn.disabled = false; btn.textContent = old; }, 18000);
}

/* ---------- 保存 ---------- */
function collect() {
  const a = JSON.parse(JSON.stringify(CFG.autoreply || {}));
  a.llm = Object.assign({}, a.llm, {
    enabled: $('llm_enabled').checked, base_url: $('base_url').value.trim(), api_key: $('api_key').value.trim(),
    model: $('model').value.trim(), temperature: +$('temperature').value, history: +$('history').value,
    persona: $('persona').value
  });
  return a;
}
function markDirty() { DIRTY = true; $('savest').textContent = '有改动没保存'; $('savebar').classList.add('show'); }
function updateSavebar() {
  const on = ['tab-llm', 'tab-persona'].includes(document.querySelector('section.tab.active')?.id);
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
    if (d.url) window.open(A(d.url), '_blank');   // 扫码登录这类动作要开新页面
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

/* ---------- 插件 = 功能（引擎能力）+ 指令插件（代码文件） ---------- */
function plugRow(name, tag, desc, enabled, kind, id, cmds) {
  const chips = (cmds && cmds.length)
    ? '<div class="chips">' + cmds.map(function (c) { return '<span class="chip">' + esc(c) + '</span>'; }).join('') + '</div>'
    : '';
  return '<div class="plug"><div class="plug-main">'
    + '<div class="plug-h"><b>' + esc(name) + '</b><code>' + esc(tag) + '</code></div>'
    + '<div class="hint">' + esc(desc) + '</div>' + chips + '</div>'
    + '<label class="switch"><span>' + (enabled ? '开' : '关') + '</span>'
    + '<input type="checkbox" ' + (enabled ? 'checked' : '')
    + ' data-kind="' + kind + '" data-id="' + esc(id) + '" onchange="toggleSwitch(this)"></label>'
    + '</div>';
}

async function loadPlugins() {
  const box = document.getElementById('pluglist');
  box.innerHTML = '<div class="hint">读取中…</div>';
  let feat = null, plug = null;
  try {
    const rs = await Promise.all([fetch(A('/admin/features')), fetch(A('/admin/plugins'))]);
    feat = await rs[0].json();
    plug = await rs[1].json();
  } catch (e) {
    box.innerHTML = '<div class="hint">读取失败（服务在重启？）</div>';
    return;
  }

  let html = '';
  if (feat && feat.ok && feat.features.length) {
    html += '<div class="sec-title">她身上的功能</div>';
    const groups = {};
    feat.features.forEach(function (f) { (groups[f.group] = groups[f.group] || []).push(f); });
    Object.keys(groups).forEach(function (g) {
      html += '<div class="sec-sub">' + esc(g) + '</div>';
      html += groups[g].map(function (f) {
        return plugRow(f.name, f.path, f.desc, f.enabled, 'feature', f.id, null);
      }).join('');
    });
  }

  if (plug && plug.ok && plug.plugins.length) {
    html += '<div class="sec-title" style="margin-top:24px">指令插件</div>';
    html += plug.plugins.map(function (p) {
      return plugRow(p.name, p.id, p.desc + ' · ' + p.count + ' 个处理器', p.enabled, 'plugin', p.id, p.commands);
    }).join('');
  }

  box.innerHTML = html || '<div class="hint">没有可显示的内容</div>';
}

async function toggleSwitch(el) {
  const kind = el.getAttribute('data-kind');
  const id = el.getAttribute('data-id');
  const on = el.checked;
  const url = kind === 'feature' ? '/admin/features/toggle' : '/admin/plugins/toggle';
  try {
    const d = await (await fetch(A(url), {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({id: id, enabled: on})
    })).json();
    toast(d.ok ? ('已' + (on ? '开启' : '关闭') + '：' + id.split('.').pop()) : ('失败：' + (d.error || '')), !d.ok);
  } catch (e) {
    toast('请求失败', true);
  }
  loadPlugins();
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
reloadConfig().then(() => { loadStatus(); loadUsage(); loadNapcat(); loadHealth(); });
setInterval(loadStatus, 8000);
setInterval(() => { if (document.querySelector('#tab-ov').classList.contains('active')) loadHealth(); }, 8000);
</script>
</body>
</html>
"""
