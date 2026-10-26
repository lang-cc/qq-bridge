"""机器人小面板：双击桌面图标打开，能启动 / 扫码登录 / 停止 / 看状态。

只显示用户该知道的东西，不堆技术细节。
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

log = logging.getLogger("panel")
log.setLevel(logging.INFO)
if not log.handlers:
    fh = logging.FileHandler(LOGS / "panel.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(fh)

API = "http://127.0.0.1:8088"


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.35) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def get_json(path: str, timeout: float = 3.0) -> dict:
    try:
        with urllib.request.urlopen(API + path, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {}


def status() -> dict:
    st = get_json("/status")
    running = bool(st.get("ok"))
    connected = bool(st.get("connected"))
    usage = get_json("/admin/usage?days=1") if running else {}
    return {
        "running": running,
        "connected": connected,
        "account": st.get("self_id") or "",
        "calls": usage.get("calls") or 0,
        "tokens": usage.get("tokens") or 0,
        "cost": usage.get("cost") or 0.0,
        "napcat": port_open(6099),
        "login": port_open(3000),
        "watchdog": port_open(9335),
    }


def run_bg(fn, *args) -> None:
    threading.Thread(target=fn, args=args, daemon=True).start()


def _pythonw() -> str:
    pyw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    return str(pyw) if pyw.exists() else sys.executable


def do_start() -> None:
    log.info("点击：启动")
    subprocess.Popen([_pythonw(), "boot.py"], cwd=str(ROOT), close_fds=True)


def do_watchdog() -> None:
    log.info("点击：开监控")
    subprocess.Popen([_pythonw(), "watchdog.py"], cwd=str(ROOT), close_fds=True)


def do_stop() -> None:
    log.info("点击：停止")
    bat = ROOT / "stop_all.bat"
    if bat.exists():
        subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(ROOT),
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def do_login() -> None:
    log.info("点击：扫码登录")
    pyw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    exe = pyw if pyw.exists() else sys.executable
    subprocess.Popen([str(exe), "login_qr.py"], cwd=str(ROOT), close_fds=True)


def do_open_logs() -> None:
    log.info("点击：查看日志")
    try:
        import os

        os.startfile(str(LOGS))
    except Exception as exc:
        log.warning("打开日志目录失败：%r", exc)


def read_llm() -> dict:
    import yaml

    try:
        cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")) or {}
        return (cfg.get("autoreply") or {}).get("llm") or {}
    except Exception as exc:
        log.warning("读配置失败：%r", exc)
        return {}


def write_llm(base_url: str, api_key: str, model: str) -> None:
    import yaml

    path = ROOT / "config.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    llm = cfg.setdefault("autoreply", {}).setdefault("llm", {})
    llm["base_url"] = base_url.strip()
    llm["api_key"] = api_key.strip()
    llm["model"] = model.strip()
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    log.info("模型配置已保存：%s / %s", llm["base_url"], llm["model"])


def test_llm(base_url: str, api_key: str, model: str) -> tuple[bool, str]:
    """用一句话试通不通，返回 (成功?, 提示)。"""
    try:
        body = json.dumps({
            "model": model.strip(),
            "messages": [{"role": "user", "content": "回复两个字：在的"}],
            "max_tokens": 64,
        }).encode()
        req = urllib.request.Request(
            base_url.strip().rstrip("/") + "/chat/completions", data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode())
        reply = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        return True, f"连通 ✅ 模型回话：{reply[:40] or '（空）'}"
    except Exception as exc:
        return False, f"连不上 ❌ {str(exc)[:80]}"


def reload_service() -> bool:
    try:
        req = urllib.request.Request(API + "/admin/reload", data=b"{}",
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            return bool(json.loads(r.read().decode()).get("ok"))
    except Exception:
        return False


def export_backup(zip_path: str) -> dict:
    """把记忆库、可读对话记录、配置、用量、日志打包成一个 zip。"""
    import sqlite3
    import tempfile
    import zipfile
    from datetime import datetime

    info = {"db": 0, "chat_files": 0, "logs": 0, "path": zip_path}
    tmpdir = Path(tempfile.mkdtemp(prefix="qqbak-"))
    personas_dir = ROOT / "data" / "personas"
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for db in sorted(personas_dir.glob("*/memory.db")):
                z.write(db, f"记忆库/{db.parent.name}/memory.db")
                info["db"] += 1
                try:
                    conn = sqlite3.connect(str(db))
                    conn.row_factory = sqlite3.Row
                    chats = conn.execute(
                        "SELECT chat_id, COUNT(*) n FROM msg GROUP BY chat_id"
                    ).fetchall()
                    for row in chats:
                        chat = row["chat_id"]
                        lines = [f"# {db.parent.name} / {chat}（共 {row['n']} 条）", ""]
                        for m in conn.execute(
                            "SELECT ts, role, content FROM msg WHERE chat_id=? ORDER BY id", (chat,)
                        ):
                            when = datetime.fromtimestamp(m["ts"]).strftime("%Y-%m-%d %H:%M")
                            who = "对方" if m["role"] == "user" else "机器人"
                            lines.append(f"[{when}] {who}：{m['content']}")
                        p = tmpdir / f"{db.parent.name}-{chat}.txt"
                        p.write_text("\n".join(lines), encoding="utf-8")
                        z.write(p, f"对话记录/{p.name}")
                        info["chat_files"] += 1
                    buf = [f"# {db.parent.name} 摘要与事实", ""]
                    for r in conn.execute("SELECT chat_id, text FROM summary"):
                        buf.append(f"[{r['chat_id']}] 摘要：{r['text']}")
                    for r in conn.execute("SELECT chat_id, key, value FROM fact"):
                        buf.append(f"[{r['chat_id']}] {r['key']}：{r['value']}")
                    if len(buf) > 2:
                        p = tmpdir / f"{db.parent.name}-摘要事实.txt"
                        p.write_text("\n".join(buf), encoding="utf-8")
                        z.write(p, f"对话记录/{p.name}")
                    conn.close()
                except Exception as exc:
                    log.warning("导出 %s 失败：%r", db, exc)

            for extra in (ROOT / "data" / "personas.yaml", ROOT / "data" / "usage.db",
                          ROOT / "config.yaml", ROOT / "data" / "memory_router.db"):
                if extra.exists():
                    z.write(extra, f"配置与数据/{extra.name}")

            for lg in sorted(LOGS.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:6]:
                z.write(lg, f"日志/{lg.name}")
                info["logs"] += 1
    finally:
        for f in tmpdir.glob("*"):
            try:
                f.unlink()
            except Exception:
                pass
        try:
            tmpdir.rmdir()
        except Exception:
            pass
    log.info("已导出备份：%s（记忆库 %d，对话记录 %d，日志 %d）",
             zip_path, info["db"], info["chat_files"], info["logs"])
    return info


def do_backup() -> None:
    from datetime import datetime
    from tkinter import filedialog, messagebox

    default = f"qq机器人备份-{datetime.now():%Y%m%d-%H%M}.zip"
    path = filedialog.asksaveasfilename(
        title="保存备份", defaultextension=".zip", initialfile=default,
        initialdir=str(Path.home() / "Desktop"), filetypes=[("压缩包", "*.zip")],
    )
    if not path:
        return
    try:
        info = export_backup(path)
        messagebox.showinfo(
            "备份完成",
            f"已保存到：\n{path}\n\n记忆库 {info['db']} 个人格\n"
            f"对话记录 {info['chat_files']} 份\n日志 {info['logs']} 个",
        )
    except Exception as exc:
        log.exception("备份失败：%r", exc)
        messagebox.showerror("备份失败", str(exc))


def open_settings(parent) -> None:
    """换 API：填地址/密钥/模型，测试没问题再保存。"""
    import tkinter as tk
    from tkinter import ttk, messagebox

    cur = read_llm()
    win = tk.Toplevel(parent)
    win.title("模型设置")
    win.geometry("540x310")
    win.transient(parent)
    try:
        win.grab_set()
    except Exception:
        pass

    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text="换一个模型接口（保存后立即生效，不用重启）",
              font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", pady=(0, 10))

    def field(label: str, value: str, secret: bool = False):
        ttk.Label(frm, text=label).pack(anchor="w")
        e = ttk.Entry(frm, width=64, show="•" if secret else "")
        e.insert(0, value or "")
        e.pack(anchor="w", pady=(2, 8))
        return e

    e_base = field("接口地址（OpenAI 兼容，通常以 /v1 结尾）", cur.get("base_url", ""))
    e_key = field("密钥", cur.get("api_key", ""), secret=True)
    e_model = field("模型名", cur.get("model", ""))

    status = ttk.Label(frm, text="", foreground="#666666", wraplength=490)
    status.pack(anchor="w")

    def do_test() -> None:
        status.config(text="测试中…", foreground="#666666")

        def work() -> None:
            ok, msg = test_llm(e_base.get(), e_key.get(), e_model.get())
            status.config(text=msg, foreground="#1a7f37" if ok else "#c0392b")

        run_bg(work)

    def do_save() -> None:
        if not (e_base.get().strip() and e_model.get().strip()):
            messagebox.showwarning("缺东西", "接口地址和模型名都要填")
            return
        try:
            write_llm(e_base.get(), e_key.get(), e_model.get())
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))
            return
        ok = reload_service()
        messagebox.showinfo("已保存", "已生效，可以继续聊了" if ok else "已写入配置，重启服务后生效")
        win.destroy()

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(12, 0))
    ttk.Button(bar, text="测试连接", command=do_test).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(bar, text="保存并生效", command=do_save).grid(row=0, column=1, padx=(0, 8))
    ttk.Button(bar, text="取消", command=win.destroy).grid(row=0, column=2)


def build_ui():
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("QQ机器人")
    root.geometry("460x340")
    root.resizable(False, False)
    try:
        root.iconbitmap(str(ROOT / "assets" / "qq-bridge.ico"))
    except Exception:
        pass

    frm = ttk.Frame(root, padding=16)
    frm.pack(fill="both", expand=True)

    title = ttk.Label(frm, text="QQ机器人", font=("Microsoft YaHei UI", 15, "bold"))
    title.pack(anchor="w")

    lbl_state = ttk.Label(frm, text="检查中…", font=("Microsoft YaHei UI", 11))
    lbl_state.pack(anchor="w", pady=(10, 2))

    lbl_detail = ttk.Label(frm, text="", font=("Microsoft YaHei UI", 9), foreground="#666666")
    lbl_detail.pack(anchor="w")

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(18, 0))

    b1 = ttk.Button(btns, text="启动", width=9, command=lambda: run_bg(do_start))
    b1.grid(row=0, column=0, padx=(0, 6), pady=4)
    b2 = ttk.Button(btns, text="扫码登录", width=9, command=lambda: run_bg(do_login))
    b2.grid(row=0, column=1, padx=(0, 6), pady=4)
    b3 = ttk.Button(btns, text="自动修复", width=9, command=lambda: run_bg(do_watchdog))
    b3.grid(row=0, column=2, padx=(0, 6), pady=4)
    b4 = ttk.Button(btns, text="停止", width=9, command=lambda: run_bg(do_stop))
    b4.grid(row=0, column=3, pady=4)

    more = ttk.Frame(frm)
    more.pack(fill="x", pady=(4, 0))
    b5 = ttk.Button(more, text="保存备份", width=10, command=lambda: run_bg(do_backup))
    b5.grid(row=0, column=0, padx=(0, 6), pady=4)
    b6 = ttk.Button(more, text="查看日志", width=10, command=lambda: run_bg(do_open_logs))
    b6.grid(row=0, column=1, padx=(0, 6), pady=4)
    b7 = ttk.Button(more, text="模型设置", width=10, command=lambda: open_settings(root))
    b7.grid(row=0, column=2, pady=4)

    hint = ttk.Label(frm, text="备份包含记忆库＋可读对话记录＋配置＋日志，可换机恢复",
                     font=("Microsoft YaHei UI", 9), foreground="#888888")
    hint.pack(anchor="w", pady=(10, 0))

    def refresh() -> None:
        s = status()
        if s["connected"]:
            lbl_state.config(text="● 运行中，QQ 已连接", foreground="#1a7f37")
            detail = f"账号 {s['account']}"
            if s["calls"]:
                detail += f"　今日 {s['calls']} 次对话　约 {s['cost']:.2f} 元"
            if not s["watchdog"]:
                detail += "　监控未开"
            lbl_detail.config(text=detail)
        elif s["running"]:
            lbl_state.config(text="● 服务已启动，等待 QQ 登录", foreground="#b8860b")
            lbl_detail.config(text="点「扫码登录」扫一下")
        elif s["napcat"]:
            lbl_state.config(text="● QQ 在启动，服务未运行", foreground="#b8860b")
            lbl_detail.config(text="点「启动」")
        else:
            lbl_state.config(text="○ 已停止", foreground="#888888")
            lbl_detail.config(text="点「启动」开始")
        root.after(3000, refresh)

    refresh()
    root.mainloop()


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass
    try:
        build_ui()
    except Exception as exc:
        log.exception("面板崩溃：%r", exc)
        raise
