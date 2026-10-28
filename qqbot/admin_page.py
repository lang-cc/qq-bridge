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
  .btn.danger.armed{background:var(--danger);border-color:var(--danger);color:#fff}
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

  /* 白名单 */
  .wl{display:flex;flex-wrap:wrap;gap:8px;margin:2px 0 0}
  .wl-item{display:inline-flex;align-items:center;gap:2px;padding:5px 5px 5px 12px;
    border-radius:999px;background:var(--surface-2);border:1px solid var(--line)}
  .wl-item i{font-style:normal;font-size:12.5px;color:var(--fg);
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
  .wl-item button{border:0;background:transparent;color:var(--dim-2);font-size:15px;line-height:1;
    padding:2px 8px;border-radius:50%;cursor:pointer}
  .wl-item button:hover{background:#fdecec;color:var(--danger)}
  .wl-add{display:flex;gap:8px;margin-top:10px;max-width:430px}
  .wl-add input{flex:1}

  /* 记忆 */
  .mem{display:grid;grid-template-columns:240px minmax(0,1fr);gap:14px}
  @media (max-width:860px){.mem{grid-template-columns:1fr}}
  .mem-sub{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:2px 0 2px 14px;padding:6px 10px;border-radius:10px;font-size:12.5px;color:var(--dim);cursor:pointer;border-left:2px solid var(--line)}
  .mem-sub:hover{background:var(--surface-2)}
  .mem-sub.active{background:var(--surface-2);color:var(--text);border-left-color:var(--accent)}
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
  @media (min-width:901px){.savebar{left:var(--side)}}
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
  /* ---------- 对齐修整：统一基线，别让卡片里各元素参差 ---------- */
  /* 1) 按钮文字默认靠左，放在 g4 网格里会像输入框 —— 一律居中 */
  .btn{justify-content:center}
  /* 1b) 行内「保存」有改动时描一圈，看得见还没存 */
  .savebtn.dirty{box-shadow:0 0 0 3px rgba(46,164,120,.22)}
  /* 2) 顶栏胶囊和按钮等高，右边缘才在一条线上 */
  .tb-r .pill,.tb-r .btn{height:32px;padding-top:0;padding-bottom:0}
  .tb-r .pill{padding-left:12px;padding-right:12px}
  /* 3) 内容区铺满，宽屏下右侧不留大片空白 */
  .content{max-width:none}
  .savebar .inner{max-width:none}
  /* 4) 白名单输入行不要太长，添加按钮紧贴输入框 */
  .wl-add{max-width:640px}
  .wl-add .btn{flex:0 0 auto;min-width:96px}
  /* 5) 用量胶囊按 3 列排，6 项正好两行，不会孤零零吊一个 */
  .chips.usage{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))}
  @media (max-width:860px){.chips.usage{grid-template-columns:repeat(2,minmax(0,1fr))}}
  @media (max-width:520px){.chips.usage{grid-template-columns:1fr}}
  .chips.usage .chip{text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  /* 6) 网格里的按钮撑满格子，四块等高等宽 */
  .grid > .btn{align-self:stretch;padding-top:12px;padding-bottom:12px}
  /* 7) 「服务在线」固定 4 列：8 项正好 4 上 4 下，宽屏也不会变成 5+3 */  .hlist{grid-template-columns:repeat(4,minmax(0,1fr))}
  @media (max-width:1500px){.hlist{grid-template-columns:repeat(2,minmax(0,1fr))}}
  @media (max-width:860px){.hlist{grid-template-columns:1fr}}
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
      <div class="d">改完点卡片右上角的「保存」，立即生效，不用重启。</div>
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
        <a class="btn ghost sm" id="napcat-link" href="http://127.0.0.1:5099" target="_blank" rel="noreferrer">协议端面板</a>
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
          <p id="needlogin-hint">用手机 QQ 扫码登录；登录成功后这一页自己会变绿，不用刷新。</p>
        </div>
      </div>
      <div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap">
        <img id="loginqr" alt="登录二维码" style="display:none;width:186px;height:186px;object-fit:contain;background:#fff;border-radius:12px;padding:8px;border:1px solid var(--line)">
        <div style="display:flex;flex-direction:column;gap:10px;min-width:180px">
          <a class="btn" id="login-open" href="http://127.0.0.1:5099" target="_blank" rel="noreferrer">打开面板扫码</a>
          <button class="btn ghost" id="login-refresh" onclick="refreshQR(this)" style="display:none">换一张二维码</button>
          <span id="loginstat" style="font-size:13px;color:var(--dim)">等待登录…</span>
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
      <div class="hint" id="actout" style="margin-top:14px;white-space:pre-wrap">扫码登录 = 到协议端面板扫码 · 掉线自愈 = 掉了自动重连 · 保存备份 = 存到 backups/</div>
    </div>

    <div class="card">
      <div class="card-h">
        <div><h2 id="proto-title">协议端面板</h2>
          <p id="proto-desc">扫码登录、看 QQ 在不在线、改连接配置都在协议端自己的面板里。</p></div>
        <div class="right">
          <button class="btn ghost sm" onclick="copyNapcat()">复制密码</button>
          <a class="btn ghost sm" id="napcat-open" href="http://127.0.0.1:5099"
             target="_blank" rel="noreferrer">打开面板</a>
        </div>
      </div>
      <div class="grid g2">
        <label class="f"><span>面板地址</span>
          <input type="text" id="napcat-url" readonly onclick="this.select()">
          <small>端口跟 protocol_backend 走：napcat→6099，snowluma→5099</small></label>
        <label class="f"><span>面板密码</span>
          <input type="text" id="napcat-token" readonly onclick="this.select()">
          <small id="proto-token-tip">打开面板时如果提示登录，把这个填进去</small></label>
      </div>
      <div class="hint" style="margin-top:12px">
        协议端在哪配的：<code>config.yaml → protocol_backend</code>（<code>napcat</code> 或 <code>snowluma</code>，
        端口差异见 <code>qqbot/proto.py</code>）。跟机器人之间的连接不变，还是 OneBot v11 反向 WS → <code>127.0.0.1:8199</code>。
      </div>
    </div>

    <div class="card">
      <div class="card-h">
        <div><h2>白名单</h2><p>只有名单里的人，它才会回话。加/删立即生效，不用重启。</p></div>
        <div class="right"><span class="chip" id="wl-state">—</span></div>
      </div>

      <div class="block-title">私聊（QQ 号）</div>
      <div class="wl" id="wl-users"><span class="hint">（还没有）</span></div>
      <div class="wl-add">
        <input type="text" id="wl-user-in" inputmode="numeric" placeholder="输入 QQ 号，回车就加">
        <button class="btn sm" onclick="wlAdd('users')">添加</button>
      </div>

      <div class="block-title">群（群号）</div>
      <div class="wl" id="wl-groups"><span class="hint">（还没有）</span></div>
      <div class="wl-add">
        <input type="text" id="wl-group-in" inputmode="numeric" placeholder="输入群号，回车就加">
        <button class="btn sm" onclick="wlAdd('groups')">添加</button>
      </div>
      <div class="hint" style="margin-top:14px">
        名单只认号码本体；点号码右边的 × 就是删掉。写进 config.yaml 的 <code>autoreply.whitelist</code>，
        注释和排版不会被覆盖。
      </div>
    </div>

    <div class="card">
      <div class="card-h"><div><h2>最近用量</h2><p>今天调用了多少次模型。</p></div>
        <div class="right"><button class="btn ghost sm" onclick="loadUsage()">刷新</button></div>
      </div>
      <div class="chips usage" id="usage"><span class="chip">—</span></div>
    </div>
  </section>

  <!-- ============ 模型 ============ -->
  <section class="tab" id="tab-llm">
    <div class="card">
      <div class="card-h">
        <div><h2>接口</h2><p>像不像真人主要看人格；这三项决定它能不能说话。</p></div>
        <div class="right">
          <button class="btn ghost sm" onclick="loadModels()">拉取可用模型</button>
          <button class="btn ghost sm" onclick="testLLM(this)">测试</button>
          <button class="btn sm savebtn" onclick="save(this)">保存</button>
        </div>
      </div>
      <div class="grid g2">
        <label class="f"><span>接口地址 base_url</span>
          <input type="text" id="base_url" placeholder="https://api.deepseek.com/v1"></label>
        <label class="f"><span>API Key</span>
          <input type="password" id="api_key" placeholder="sk-…" autocomplete="off">
          <small><a href="javascript:void(0)" onclick="peekKey()">显示 / 隐藏</a></small></label>
      </div>
      <div style="margin-top:14px">
        <label class="f"><span>模型名</span>
          <select id="model" onchange="markDirty()"><option value="">点右上「拉取可用模型」</option></select>
          <small id="modelhint">列表来自接口的 /models；想填列表外的模型名，直接改 config.yaml</small></label>
      </div>
      <div class="chips" id="modelchips" style="margin-top:12px"></div>
      <pre class="out" id="llmtest" style="display:none;margin-top:14px"></pre>
      <div class="hint" style="margin-top:14px">
        要不要她说话、打字机快慢这些不在这儿：改 config.yaml 里的
        <code>autoreply.llm.enabled</code>（总开关）和 <code>autoreply.typing</code>（每字多少毫秒）。
      </div>
    </div>

    <div class="card">
      <div class="card-h">
        <div><h2>语音合成</h2><p>想让她发语音才填；全留空就只发文字。</p></div>
        <div class="right">
          <span class="chip" id="ttsstate">未配置</span>
          <button class="btn ghost sm" onclick="testTTS(this)">测试</button>
          <button class="btn sm savebtn" onclick="save(this)">保存</button>
        </div>
      </div>
      <div class="grid g3">
        <label class="f"><span>提供方</span>
          <select id="tts_provider" onchange="markDirty()">
            <option value="">（不用语音，留空）</option>
            <option value="aliyun">阿里云 DashScope</option>
            <option value="edge">Edge TTS（免费，不用 key）</option>
            <option value="volc">火山引擎</option>
            <option value="baidu">百度（免费）</option>
            <option value="sapi">本机离线</option>
          </select></label>
        <label class="f"><span>语音模型</span>
          <input type="text" id="tts_model" placeholder="cosyvoice-v3.5-plus / qwen3-tts-flash" oninput="markDirty()">
          <small>edge / baidu / 本机不用填</small></label>
        <label class="f"><span>音色 ID</span>
          <input type="text" id="tts_voice" placeholder="cosyvoice-v3.5-plus-xxxx 或 zh-CN-XiaoyiNeural" oninput="markDirty()"></label>
      </div>
      <div class="grid g2" style="margin-top:14px">
        <label class="f"><span>API Key</span>
          <input type="password" id="tts_api_key" placeholder="sk-…（阿里云必填，edge/百度/本机不用）" autocomplete="off" oninput="markDirty()">
          <small><a href="javascript:void(0)" onclick="peekTTSKey()">显示 / 隐藏</a>　火山引擎的话在 config.yaml 里填 appid / token</small></label>
        <label class="f"><span>接口地址</span>
          <input type="text" id="tts_base_url" placeholder="留空 = 官方地址（阿里云 dashscope）" oninput="markDirty()">
          <small>只在自建 / 代理语音接口时填，填到根地址就行</small></label>
      </div>
      <pre class="out" id="ttstest" style="display:none;margin-top:14px"></pre>
    </div>
  </section>

  <!-- ============ 人格 ============ -->
  <section class="tab" id="tab-persona">
    <div class="card">
      <div class="card-h">
        <div><h2>人格</h2><p>她是谁、怎么说话、和你什么关系 —— 这一段最重要，写得越像真人越好。</p></div>
        <div class="right">
          <span class="chip" id="pcount">0 字</span>
          <button class="btn danger sm" id="pclear" onclick="clearPersona(this)">清空</button>
          <button class="btn sm savebtn" onclick="save(this)">保存</button>
        </div>
      </div>
      <label class="f"><textarea id="persona" placeholder="你是…"
        oninput="document.getElementById('pcount').textContent=this.value.length+' 字'"></textarea></label>
      <div class="hint" style="margin-top:10px">
        只改这段文字 = 改「当前人格」的说法。一个 QQ 号固定一个人格，第一次聊天时自动绑定，之后不能换；
        QQ 里发 <b>人格</b> 可以看她是谁，<b>记忆</b> 看她记得你什么，<b>忘记我</b> 清空当前会话。
        <br>「清空」只清这段文字：<b>人格、记忆、绑定关系都不动</b>（记忆在 <code>data/personas/&lt;人格&gt;/memory.db</code>，
        只有「记忆」页的<b>清空这段</b>才会删），清完要再点一次<b>保存</b>才生效。切人格同理 —— 换回去记忆还在。
      </div>
    </div>
  </section>

  <!-- ============ 功能 ============ -->
  <section class="tab" id="tab-plug">
    <div class="card">
      <div class="card-h">
        <div><h2>节奏</h2>
          <p>回话快慢、多久不回、群里多安静。改完点保存，立即生效，不用重启。</p></div>
        <div class="right"><button class="btn sm savebtn" onclick="save(this)">保存</button></div>
      </div>
      <div class="grid g4">
        <label class="f"><span>最快回（秒）</span>
          <input type="number" id="rd_min" min="0" max="100" step="1" oninput="markDirty()"><small>再快也别秒回</small></label>
        <label class="f"><span>最慢回（秒）</span>
          <input type="number" id="rd_max" min="0" max="100" step="1" oninput="markDirty()"><small>深夜会按作息再乘几倍</small></label>
        <label class="f"><span>平时不回（%）</span>
          <input type="number" id="ig_chance" min="0" max="100" step="1" oninput="markDirty()"><small>已读不回的概率</small></label>
        <label class="f"><span>惹生气后不回（%）</span>
          <input type="number" id="ig_angry" min="0" max="100" step="1" oninput="markDirty()"><small>被凶之后基本不理你</small></label>
        <label class="f"><span>群里回话（%）</span>
          <input type="number" id="gprob" min="0" max="100" step="5" oninput="markDirty()"><small>群里没 @ 也说话的概率</small></label>
        <label class="f"><span>只说半句（%）</span>
          <input type="number" id="hl_short" min="0" max="100" step="1" oninput="markDirty()"><small>只留前半句</small></label>
        <label class="f"><span>话说一半（%）</span>
          <input type="number" id="hl_half" min="0" max="100" step="1" oninput="markDirty()"><small>「因为你这个…算了」</small></label>
        <label class="f"><span>拆两条发（%）</span>
          <input type="number" id="hl_burst" min="0" max="100" step="1" oninput="markDirty()"><small>说完停一下再补一句</small></label>
        <label class="f"><span>多久算断线（秒）</span>
          <input type="number" id="cu_gap" min="0" max="3600" step="10" oninput="markDirty()"><small>低于这个不触发掉线补偿</small></label>
        <label class="f"><span>自己上网间隔（小时）</span>
          <input type="number" id="wd_hours" min="1" max="48" step="1" oninput="markDirty()"><small>多久自己刷一次热梗</small></label>
        <label class="f"><span>每多少条复盘</span>
          <input type="number" id="mem_reflect" min="0" max="200" step="1" oninput="markDirty()"><small>记进长期记忆的频率</small></label>
        <label class="f"><span>普通记忆留几天</span>
          <input type="number" id="mem_retain" min="1" max="3650" step="1" oninput="markDirty()"><small>重要原话永久留着</small></label>
      </div>
    </div>
    <div class="card">
      <div class="card-h">
        <div><h2>时间</h2>
          <p>记多久、几点写日记、几点别出声 —— 改完点保存。</p></div>
        <div class="right"><button class="btn sm savebtn" onclick="save(this)">保存</button></div>
      </div>
      <div class="grid g4">
        <label class="f"><span>记仇多久（小时）</span>
          <input type="number" id="grudge_hours" min="0" max="100" step="1" oninput="markDirty()"><small>过了就忘</small></label>
        <label class="f"><span>写日记时间（点）</span>
          <input type="number" id="diary_hour" min="0" max="100" step="1" oninput="markDirty()"><small>0-23，睡前那会儿</small></label>
        <label class="f"><span>免打扰开始（点）</span>
          <input type="number" id="quiet_start" min="0" max="23" step="1" oninput="markDirty()"><small>自己不开聊</small></label>
        <label class="f"><span>免打扰结束（点）</span>
          <input type="number" id="quiet_end" min="0" max="23" step="1" oninput="markDirty()"><small>自己不开聊</small></label>
        <label class="f"><span>主动开聊最短（分钟）</span>
          <input type="number" id="pmin" min="5" max="1440" step="5" oninput="markDirty()"><small>多久至少找你一次</small></label>
        <label class="f"><span>主动开聊最长（分钟）</span>
          <input type="number" id="pmax" min="5" max="2880" step="5" oninput="markDirty()"><small>最久多久没找你</small></label>
        <label class="f"><span>每天最多主动（次）</span>
          <input type="number" id="pmaxday" min="0" max="50" step="1" oninput="markDirty()"><small>别烦人</small></label>
        <label class="f"><span>表情包概率（%）</span>
          <input type="number" id="sticker_pct" min="0" max="100" step="1" oninput="markDirty()"><small>短句会加码</small></label>
        <label class="f"><span>打错字概率（%）</span>
          <input type="number" id="typo_pct" min="0" max="100" step="1" oninput="markDirty()"><small>手滑</small></label>
        <label class="f"><span>看完过会儿再回（%）</span>
          <input type="number" id="read_delay_pct" min="0" max="100" step="1" oninput="markDirty()"><small>已读不回一阵</small></label>
      </div>
    </div>
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
          <button class="btn ghost sm" onclick="downloadMem()">下载记忆</button>
          <button class="btn sm savebtn" onclick="save(this)">保存设置</button>
          <button class="btn danger sm" onclick="clearMem(this)">清空这段</button>
        </div>
      </div>
      <div class="grid g4" style="margin-bottom:14px">
        <label class="f"><span>自动备份间隔（小时）</span>
          <input type="number" id="backup_hours" min="0" max="720" step="1" oninput="markDirty()"><small>0 = 不自动备份</small></label>
        <label class="f"><span>备份保留份数</span>
          <input type="number" id="backup_keep" min="1" max="200" step="1" oninput="markDirty()"><small>超出的自动删旧的</small></label>
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
  $('base_url').value = llm.base_url || '';
  $('api_key').value = llm.api_key || '';
  setModelValue(llm.model || '');
  // 温度 / 记忆轮数先从页面拿掉（等安排位置），config.yaml 里的值原样不动
  $('persona').value = llm.persona || '';
  $('pcount').textContent = ($('persona').value || '').length + ' 字';
  /* 语音合成：没配就是空的，留空不影响文字回复 */
  /* 节奏卡：数值 / 概率（页面按 0-100 显示） */
  const rd = a.reply_delay || {}, igc = a.ignore || {}, hl = a.humanlike || {};
  const cu = a.catchup || {}, wd = a.wander || {}, mm = a.memory || {};
  const setv = (id, v) => { const el = $(id); if (el) el.value = v; };
  setv('rd_min', rd.min ?? 2);
  setv('rd_max', rd.max ?? 15);
  setv('ig_chance', Math.round((igc.chance ?? 0.04) * 100));
  setv('ig_angry', Math.round((igc.angry_skip ?? 0.8) * 100));
  setv('gprob', Math.round((a.group_reply_probability ?? 0.7) * 100));
  setv('hl_short', Math.round((hl.short_chance ?? 0.12) * 100));
  setv('hl_half', Math.round((hl.half_chance ?? 0.06) * 100));
  setv('hl_burst', Math.round((hl.burst_chance ?? 0.15) * 100));
  setv('cu_gap', cu.min_gap_seconds ?? 60);
  setv('wd_hours', wd.hours ?? 3);
  setv('mem_reflect', mm.reflect_every ?? 5);
  setv('mem_retain', mm.retain_days ?? 14);
  setv('diary_hour', mm.diary_hour ?? 23);
  setv('backup_hours', mm.backup_hours ?? 6);
  setv('backup_keep', mm.backup_keep ?? 20);
  setv('grudge_hours', (a.grudge || {}).hours ?? 10);
  const pv = a.proactive || {};
  setv('pmin', pv.min_minutes ?? 45);
  setv('pmax', pv.max_minutes ?? 180);
  setv('quiet_start', pv.quiet_start ?? 23);
  setv('quiet_end', pv.quiet_end ?? 8);
  setv('pmaxday', pv.max_per_day ?? 6);
  setv('sticker_pct', Math.round(((a.stickers || {}).probability ?? 0.35) * 100));
  setv('typo_pct', Math.round(((a.playful || {}).typo_chance ?? 0.05) * 100));
  setv('read_delay_pct', Math.round(((a.playful || {}).read_delay_chance ?? 0.06) * 100));
  const tt = a.tts || {};
  $('tts_provider').value = tt.provider || '';
  $('tts_model').value = tt.model || '';
  $('tts_voice').value = tt.voice || '';
  $('tts_api_key').value = tt.api_key || '';
  $('tts_base_url').value = tt.base_url || '';
  $('ttsstate').textContent = tt.provider
    ? (tt.provider + (tt.model ? ' · ' + tt.model : '')) : '未配置';
  // 白名单（在 autoreply.whitelist 里，页面上能直接加/删）
  const allow = a.whitelist || CFG.allow || {};
  WL = {users: (allow.users || []).map(String), groups: (allow.groups || []).map(String)};
  renderWL('users'); renderWL('groups');
  $('st-allow').textContent = WL.users.length;
  document.querySelectorAll('#tab-llm input,#tab-persona textarea').forEach(el => el.oninput = markDirty);
  DIRTY = false;
  $('savest').textContent = '（没有改动）';
  updateSavebar();
}

/* ---------- 白名单：网页上直接加/删，存盘即生效 ---------- */
let WL = {users: [], groups: []};
let PROTO = {};          // 协议端信息（/admin/napcat）：kind / label / has_qr
function renderWL(kind) {
  const box = $(kind === 'users' ? 'wl-users' : 'wl-groups');
  if (!box) return;
  const list = WL[kind] || [];
  box.innerHTML = list.length ? list.map(v =>
    `<span class="wl-item"><i>${esc(v)}</i>` +
    `<button title="从白名单删掉" onclick="wlRemove('${kind}','${esc(v)}')">×</button></span>`
  ).join('') : '<span class="hint">（还没有，下面加一个）</span>';
  const st = $('wl-state');
  if (st) st.textContent = WL.users.length + ' 人 · ' + WL.groups.length + ' 群';
}
async function wlSave(kind, values, tip) {
  try {
    const d = await (await fetch(A('/admin/whitelist'), {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({kind: kind, values: values})
    })).json();
    if (!d.ok) { toast('失败：' + (d.error || ''), true); renderWL(kind); return false; }
    WL = {users: d.whitelist.users, groups: d.whitelist.groups};
    renderWL('users'); renderWL('groups');
    $('st-allow').textContent = WL.users.length;
    toast(tip);
    return true;
  } catch (e) {
    toast('请求失败（服务在重启？）', true);
    return false;
  }
}
async function wlAdd(kind) {
  const inp = $(kind === 'users' ? 'wl-user-in' : 'wl-group-in');
  const v = (inp.value || '').trim();
  if (!/^\d{4,13}$/.test(v)) return toast('要纯数字的 QQ 号 / 群号', true);
  if ((WL[kind] || []).includes(v)) { inp.value = ''; return toast('已经在名单里了', true); }
  if (await wlSave(kind, (WL[kind] || []).concat([v]), '已加入：' + v)) inp.value = '';
}
async function wlRemove(kind, v) {
  if (!confirm('把 ' + v + ' 从白名单删掉？删掉后这个号发消息她就不回了')) return;
  await wlSave(kind, (WL[kind] || []).filter(x => x !== v), '已删除：' + v);
}
['wl-user-in', 'wl-group-in'].forEach(id => {
  const el = $(id);
  if (el) el.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); wlAdd(id === 'wl-user-in' ? 'users' : 'groups'); }
  });
});

/* ---------- NapCat 面板信息 ---------- */
async function loadNapcat() {
  try {
    const d = await (await fetch(A('/admin/napcat'))).json();
    if (!d.ok) return;
    PROTO = d;
    // SnowLuma 的 WebUI 密码每次重启都会重新生成，后端会从 logs/stdout.log 里捞最新的
    const autoPass = d.webui_pass || '';
    $('napcat-url').value = d.url;
    $('napcat-token').value = autoPass || d.token || (d.kind === 'napcat' ? '（没设密码）' : '（面板里自己设的登录密码，这里没存）');
    $('napcat-open').href = d.webui || d.url;
    $('napcat-link').href = d.webui || d.url;
    $('napcat-link').textContent = (d.label || '协议端') + ' 面板';
    if ($('proto-title')) $('proto-title').textContent = (d.label || '协议端') + ' 面板';
    if ($('proto-desc')) {
      $('proto-desc').textContent = d.has_qr
        ? '扫码登录、看 QQ 在不在线、改连接配置都在这里。手机 QQ 扫面板里的二维码即可。'
        : `扫码登录、看 QQ 在不在线、改连接配置都在 ${d.label} 自己的面板（${d.host}:${d.port}）里。`;
    }
    if ($('proto-token-tip')) {
      if (autoPass) {
        $('proto-token-tip').textContent =
          `面板登录：${d.webui_user || 'admin'} / ${autoPass}（每次重启会变，这里自动读最新的）`;
      } else {
        $('proto-token-tip').textContent = d.has_qr
          ? '打开面板时如果提示登录，把这个填进去'
          : '没填就是面板里自己设的登录密码；填了 config.yaml 的 protocol.webui_token 就能一键带密码打开';
      }
    }
    if (d.qq_running === false && $('proto-desc')) {
      $('proto-desc').textContent = `QQ 进程没在跑 —— 先双击打开 QQ，再到 ${d.label} 面板里扫码登录。`;
    }
    // 只有 NapCat 会吐二维码图片；SnowLuma 在面板/桌面里扫
    const qr = $('loginqr');
    if (qr) qr.style.display = d.has_qr ? '' : 'none';
    if ($('login-refresh')) $('login-refresh').style.display = d.has_qr ? '' : 'none';
    if ($('login-open')) {
      $('login-open').textContent = d.has_qr ? '打开面板扫码' : `打开 ${d.label} 面板扫码`;
      $('login-open').href = d.webui || d.url;
    }
    if ($('needlogin-hint') && !d.has_qr) {
      $('needlogin-hint').textContent = `在 ${d.label} 面板里用手机 QQ 扫码登录；登录成功后这一页自己会变绿。`;
    }
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
    // 没登录就在这一页直接显示二维码（只有 NapCat 有本地二维码；SnowLuma 给个「打开面板」按钮）
    if (!st.connected) {
      const q = $('loginqr');
      const hasQR = !PROTO || PROTO.has_qr !== false;
      if (q && hasQR && Date.now() - (window.__qrAt || 0) > 4000) {
        q.src = A('/admin/qr.png') + '&t=' + Date.now();
        window.__qrAt = Date.now();
      }
      if ($('loginstat')) {
        $('loginstat').textContent = hasQR ? '等待扫码…'
          : '在 ' + ((PROTO && PROTO.label) || '协议端') + ' 面板里扫码登录';
      }
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

/* ---------- 清空人格（两段式确认） ---------- */
let PCLEAR_T = null;
function clearPersona(btn) {
  if (btn.dataset.armed !== '1') {          // 第一次点：只是上膛，不动内容
    btn.dataset.armed = '1';
    btn.textContent = '真的清空？再点一次';
    btn.classList.add('armed');
    clearTimeout(PCLEAR_T);
    PCLEAR_T = setTimeout(() => {           // 10 秒没再点，自己退回去
      btn.dataset.armed = '';
      btn.classList.remove('armed');
      btn.textContent = '清空';
    }, 10000);
    return;
  }
  clearTimeout(PCLEAR_T);                   // 第二次点：真清
  btn.dataset.armed = '';
  btn.classList.remove('armed');
  btn.textContent = '已清空';
  $('persona').value = '';
  $('pcount').textContent = '0 字';
  markDirty();                              // 空也是改动，要点保存才写进配置
  toast('文字已清空 · 记忆和绑定都没动，记得点「保存」');
  setTimeout(() => { btn.textContent = '清空'; }, 1600);
}

/* ---------- 保存 ---------- */
function collect() {
  const a = JSON.parse(JSON.stringify(CFG.autoreply || {}));
  // 只覆盖页面上有的字段；enabled（要不要回话）和 typing（打字机）归 config.yaml 管，原样带回去
  a.llm = Object.assign({}, a.llm, {
    base_url: $('base_url').value.trim(), api_key: $('api_key').value.trim(),
    model: $('model').value.trim(), persona: $('persona').value
  });
  /* 语音：只覆盖页面上有的字段，appid/token/cluster/voice_type 这些还在 config.yaml 里 */
  a.tts = Object.assign({}, a.tts, {
    provider: $('tts_provider').value.trim(), model: $('tts_model').value.trim(),
    voice: $('tts_voice').value.trim(), api_key: $('tts_api_key').value.trim(),
    base_url: $('tts_base_url').value.trim()
  });
  // 「节奏」卡：数值直接落进 config，百分比在页面上填 0-100
  const num = (id, dflt) => { const v = parseFloat($(id).value); return isFinite(v) ? v : dflt; };
  const pct = (id, dflt) => Math.max(0, Math.min(100, num(id, dflt))) / 100;
  a.reply_delay = Object.assign({}, a.reply_delay, {
    min: Math.max(0, num('rd_min', 2)), max: Math.max(0, num('rd_max', 15))
  });
  if (a.reply_delay.max < a.reply_delay.min) a.reply_delay.max = a.reply_delay.min;
  a.ignore = Object.assign({}, a.ignore, {
    chance: pct('ig_chance', 4), angry_skip: pct('ig_angry', 80)
  });
  a.group_reply_probability = pct('gprob', 70);
  a.humanlike = Object.assign({}, a.humanlike, {
    short_chance: pct('hl_short', 12), half_chance: pct('hl_half', 6), burst_chance: pct('hl_burst', 15)
  });
  a.catchup = Object.assign({}, a.catchup, {min_gap_seconds: Math.max(0, num('cu_gap', 60))});
  a.wander = Object.assign({}, a.wander, {hours: Math.max(1, num('wd_hours', 3))});
  a.memory = Object.assign({}, a.memory, {
    reflect_every: Math.max(0, num('mem_reflect', 5)), retain_days: Math.max(1, num('mem_retain', 14)),
    diary_hour: Math.max(0, Math.min(23, num('diary_hour', 23))),
    backup_hours: Math.max(0, num('backup_hours', 6)), backup_keep: Math.max(1, num('backup_keep', 20))
  });
  a.grudge = Object.assign({}, a.grudge, {hours: Math.max(0, num('grudge_hours', 10))});
  a.proactive = Object.assign({}, a.proactive, {
    min_minutes: Math.max(5, num('pmin', 45)), max_minutes: Math.max(5, num('pmax', 180)),
    quiet_start: Math.max(0, Math.min(23, num('quiet_start', 23))),
    quiet_end: Math.max(0, Math.min(23, num('quiet_end', 8))),
    max_per_day: Math.max(0, num('pmaxday', 6))
  });
  a.stickers = Object.assign({}, a.stickers, {probability: pct('sticker_pct', 35)});
  a.playful = Object.assign({}, a.playful, {
    typo_chance: pct('typo_pct', 5), read_delay_chance: pct('read_delay_pct', 6)
  });
  return a;
}
/* 保存按钮跟着卡片走：模型、语音、人格各一个，改哪儿存哪儿；
   右下角那条保存栏照旧留着 —— 它是全页的，还带着「撤销」。 */
function markSaveBtns(state) {   // 'idle' | 'dirty' | 'saved' | 'busy' | 'error'
  const label = {idle: '保存', dirty: '保存 ·', saved: '已保存', busy: '保存中…', error: '重试'}[state] || '保存';
  document.querySelectorAll('.savebtn').forEach(b => {
    b.textContent = label;
    b.classList.toggle('dirty', state === 'dirty');
    b.title = state === 'dirty' ? '有改动，点这里保存' : '';
  });
}
function markDirty() {
  DIRTY = true;
  markSaveBtns('dirty');
  $('savest').textContent = '有改动没保存';
  updateSavebar();
}
function updateSavebar() {
  // 行内按钮能解决的两个页面就不弹右下角那条了
  const on = document.querySelector('section.tab.active')?.id === 'tab-persona';
  $('savebar').classList.toggle('show', on);
}
async function save(btn) {
  markSaveBtns('busy');
  $('savest').textContent = '保存中…';
  let d = {};
  try {
    const r = await fetch(A('/admin/save'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({autoreply: collect()})});
    d = await r.json();
  } catch (e) { d = {ok: false, error: String(e)}; }
  if (d.ok) {
    CFG.autoreply = collect();
    DIRTY = false;
    markSaveBtns('saved');
    setTimeout(() => markSaveBtns('idle'), 1600);
    $('savest').textContent = '已保存 ' + new Date().toLocaleTimeString();
    const t = (CFG.autoreply || {}).tts || {};
    if ($('ttsstate')) $('ttsstate').textContent = t.provider ? (t.provider + (t.model ? ' · ' + t.model : '')) : '未配置';
    toast('已保存，立即生效');
  } else {
    markSaveBtns('error');
    $('savest').textContent = '保存失败';
    toast('保存失败：' + (d.error || ''), true);
  }
}
document.addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); save(); } });

/* ---------- 模型 ---------- */
function peekKey() { const el = $('api_key'); el.type = el.type === 'password' ? 'text' : 'password'; }
/* 下拉里没有就临时补一个（配置里写了列表外的模型名时用） */
function setModelValue(v) {
  const sel = $('model');
  if (!sel) return;
  v = (v || '').trim();
  if (v && !Array.from(sel.options).some(o => o.value === v)) {
    const o = document.createElement('option');
    o.value = v; o.textContent = v; sel.appendChild(o);
  }
  sel.value = v;
}
/* 保存前先测一遍：密钥通不通、模型名对不对、能不能真说出一句话。
   用的是【表单里当前的值】，不是已保存的配置 —— 换完 key 直接就能验。 */
async function testLLM(btn) {
  const box = $('llmtest');
  box.style.display = '';
  box.textContent = '正在测：① 用 /models 验密钥 → ② 让它说一句话…';
  if (btn) { btn.disabled = true; btn.textContent = '测试中…'; }
  try {
    const r = await fetch(A('/admin/test'), {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({autoreply: collect(), text: '用一句话跟我打个招呼'})
    });
    const d = await r.json();
    const L = [];
    L.push((d.ok ? '✅ 通过，这套配置能用' : '❌ 没通过，先别保存') + `\n地址 ${d.base_url || '(空)'}　模型 ${d.model || '(空)'}`);
    if (d.key_ok === true) L.push('密钥　✅ ' + (d.key_msg || '有效'));
    else if (d.key_ok === false) L.push('密钥　❌ ' + (d.key_msg || '无效'));
    else if (d.key_msg) L.push('密钥　• ' + d.key_msg);
    if (d.model_found === false) L.push('模型　⚠️ 接口的模型列表里没有这个名字');
    if (d.ok) {
      L.push(`耗时　${d.ms} ms　tokens ${d.tokens || '?'}`);
      L.push('它说　' + (d.reply || '(空)'));
    }
    if (d.error) L.push('问题　' + d.error);
    if (d.hint) L.push('怎么办　' + d.hint);
    box.textContent = L.join('\n');
    toast(d.ok ? '测试通过，可以保存' : '测试没通过，看页面上的那几行', !d.ok);
  } catch (e) {
    box.textContent = '测试请求本身失败了：' + e;
    toast('测试请求失败', true);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '测试一下'; }
  }
}
/* 语音合成也测一下：真合成一条，回耗时 + 文件大小 */
function peekTTSKey() { const el = $('tts_api_key'); el.type = el.type === 'password' ? 'text' : 'password'; }
async function testTTS(btn) {
  const box = $('ttstest');
  box.style.display = '';
  box.textContent = '正在合成一句「测试一下，一二三」…';
  if (btn) { btn.disabled = true; btn.textContent = '合成中…'; }
  try {
    const r = await fetch(A('/admin/test_tts'), {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({autoreply: collect()})
    });
    const d = await r.json();
    const L = [];
    L.push((d.ok ? '✅ 语音通了' : '❌ 没通')
      + `　提供方 ${d.provider || '(未填)'}　模型 ${d.model || '(未填)'}　音色 ${d.voice || '(未填)'}`);
    if (d.ok) {
      L.push(`耗时　${d.ms} ms`);
      L.push(`文件　${d.file || ''}　${d.size ? Math.round(d.size / 1024) + ' KB' : ''}`);
    }
    if (d.error) L.push('问题　' + d.error);
    if (d.hint) L.push('怎么办　' + d.hint);
    box.textContent = L.join('\n');
    toast(d.ok ? '语音正常，可以保存' : '语音没通，看页面上的那几行', !d.ok);
  } catch (e) {
    box.textContent = '测试请求本身失败了：' + e;
    toast('测试请求失败', true);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '测一下'; }
  }
}
async function loadModels() {
  toast('正在拉取模型列表…');
  const r = await fetch(A('/admin/models')); const d = await r.json();
  if (!d.ok) { toast('拉取失败：' + (d.error || ''), true); return; }
  const sel = $('model');
  const cur = sel.value;
  const rows = (d.detail && d.detail.length) ? d.detail : (d.models || []).map(id => ({id: id, name: '', context: 0}));
  const fmtCtx = n => !n ? '' : (n >= 1048576 ? (n / 1048576).toFixed(0) + 'M'
    : n >= 1024 ? Math.round(n / 1024) + 'K' : String(n));
  sel.innerHTML = rows.map(m =>
    `<option value="${esc(m.id)}">${esc(m.name && m.name !== m.id ? m.id + ' · ' + m.name : m.id)}</option>`
  ).join('') || '<option value="">（接口没给模型列表）</option>';
  setModelValue(cur || (rows[0] && rows[0].id) || '');
  $('modelchips').innerHTML = rows.map(m => {
    const t = [m.name, m.context ? '上下文 ' + fmtCtx(m.context) : ''].filter(Boolean).join(' · ');
    return `<span class="chip click" title="${esc(t)}" onclick="setModelValue('${esc(m.id)}');markDirty()">${esc(m.id)}</span>`;
  }).join('');
  // 这行小字顺便说明"这些就是接口返回的全部"，省得以为被截断了
  const ctxs = [...new Set(rows.map(m => fmtCtx(m.context)).filter(Boolean))];
  if ($('modelhint')) {
    $('modelhint').textContent = `接口 ${d.endpoint || '/models'} 就只返回这 ${d.count ?? rows.length} 个`
      + (ctxs.length ? `（上下文 ${ctxs.join(' / ')}）` : '') + '；要填列表外的模型名直接改 config.yaml';
  }
  toast('接口返回 ' + (d.count ?? rows.length) + ' 个模型');
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
  const name = (cid) => cid.startsWith('u') ? ('QQ ' + cid.slice(1))
    : cid.startsWith('g') ? ('群 ' + cid.slice(1)) : cid;
  $('memlist').innerHTML = d.chats.map((c, i) => {
    const ps = c.personas || [];
    const subs = ps.length ? ps.map((p, j) =>
      `<div class="mem-sub" data-c="${i}" data-p="${j}">
         <span>${esc(p.persona || '默认')}</span><i>${p.count}</i></div>`).join('') : '';
    return `<div class="mem-item${i === 0 ? ' active' : ''}" data-i="${i}">
       <span style="flex:1">${esc(name(c.chat))}</span>
       <i>${c.count}${ps.length > 1 ? ' · ' + ps.length + ' 个人格 ▾' : (ps.length === 1 ? ' · ' + esc(ps[0].persona) : '')}</i>
       <button class="btn danger sm mem-del" data-c="${i}">删除</button>
     </div>
     <div class="mem-subs" id="subs${i}" style="display:none">${subs}</div>`;
  }).join('');
  document.querySelectorAll('.mem-del').forEach(btn => btn.onclick = async (ev) => {
    ev.stopPropagation();
    const c = d.chats[+btn.dataset.c];
    const now = Date.now();
    if (btn.dataset.arm !== c.chat || now - (+btn.dataset.ts || 0) > 8000) {
      btn.dataset.arm = c.chat; btn.dataset.ts = now;
      btn.textContent = '真删？再点'; btn.classList.add('armed');
      setTimeout(() => {
        if (Date.now() - (+btn.dataset.ts || 0) >= 8000) {
          btn.textContent = '删除'; btn.classList.remove('armed'); btn.dataset.arm = '';
        }
      }, 8200);
      return;
    }
    btn.textContent = '删除中…'; btn.classList.remove('armed');
    const r = await fetch(A('/admin/memory/clear'), {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({persona: '', chat: c.chat})});
    const j = await r.json();
    toast(j.ok ? ('已删除 ' + (c.chat) + ' 的全部记忆') : ('失败：' + (j.error || '')), !j.ok);
    loadMemList();
  });
  document.querySelectorAll('.mem-item').forEach(el => el.onclick = () => {
    const i = +el.dataset.i, box = $('subs' + i);
    document.querySelectorAll('.mem-item').forEach(x => x.classList.toggle('active', x === el));
    document.querySelectorAll('.mem-subs').forEach((b, k) => { if (k !== i) b.style.display = 'none'; });
    const c = d.chats[i], ps = c.personas || [];
    if (ps.length > 1) {
      const open = box.style.display !== 'none';
      box.style.display = open ? 'none' : 'block';
      if (!open) return;                 // 展开人格，先不选具体那个
    }
    showMem({persona: (ps[0] || {}).persona || '', chat: c.chat});
  });
  document.querySelectorAll('.mem-sub').forEach(el => el.onclick = (ev) => {
    ev.stopPropagation();
    const c = d.chats[+el.dataset.c], p = (c.personas || [])[+el.dataset.p] || {};
    document.querySelectorAll('.mem-sub').forEach(x => x.classList.toggle('active', x === el));
    showMem({persona: p.persona || '', chat: c.chat});
  });
  const first = d.chats[0], fps = first.personas || [];
  MEMSEL = {persona: (fps[0] || {}).persona || '', chat: first.chat};
  showMem(MEMSEL);
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
let CLEAR_ARM = 0, CLEAR_CHAT = '';
async function clearMem(btn) {
  if (!MEMSEL) return toast('先选一个会话', true);
  const now = Date.now();
  if (CLEAR_CHAT !== MEMSEL.chat || now - CLEAR_ARM > 8000) {
    CLEAR_CHAT = MEMSEL.chat;
    CLEAR_ARM = now;
    if (btn) { btn.textContent = '真的清空？再点一次'; btn.classList.add('armed'); }
    setTimeout(() => {
      if (Date.now() - CLEAR_ARM >= 8000 && btn) { btn.textContent = '清空这段'; btn.classList.remove('armed'); }
    }, 8200);
    return;
  }
  CLEAR_ARM = 0; CLEAR_CHAT = '';
  if (btn) { btn.textContent = '清空这段'; btn.classList.remove('armed'); }
  const r = await fetch(A('/admin/memory/clear'), {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({persona: MEMSEL.persona, chat: MEMSEL.chat})});
  const d = await r.json();
  toast(d.ok ? '已清空' : '失败：' + (d.error || ''), !d.ok);
  loadMemList();
}

async function downloadMem() {
  toast('打包中…');
  try {
    const r = await fetch(A('/admin/memory/export'));
    if (!r.ok) return toast('打包失败', true);
    const b = await r.blob();
    const a = document.createElement('a');
    const d = new Date();
    const stamp = d.getFullYear() + String(d.getMonth() + 1).padStart(2, '0') + String(d.getDate()).padStart(2, '0')
      + '-' + String(d.getHours()).padStart(2, '0') + String(d.getMinutes()).padStart(2, '0');
    a.href = URL.createObjectURL(b);
    a.download = 'memory-' + stamp + '.zip';
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    toast('已开始下载');
  } catch (e) { toast('打包失败：' + e, true); }
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
