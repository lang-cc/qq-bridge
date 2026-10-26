"""首次设置向导：客户填 4 页，配置自动生成，不用碰 yaml。

客户只需要提供三样东西（其余全自动）：
1. 机器人用的 QQ 号 + 要聊的人
2. 模型 API（地址 / 密钥 / 模型名）
3. 人格设定（名字、身份、说话风格、和你的关系）
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent

LIFE_TEMPLATE = [
    {"key": "sleep", "from": 1, "to": 8, "label": "睡觉",
     "hint": "你还在睡，被消息吵醒时句子很短、有点迷糊", "delay": [15, 60], "short": True},
    {"key": "work", "from": 8, "to": 17, "label": "忙",
     "hint": "你在忙自己的事，回得慢、话短", "delay": [12, 45], "short": True},
    {"key": "free", "from": 17, "to": 22, "label": "空闲",
     "hint": "你闲下来了，最有空聊天，话最多也最有耐心", "delay": [1, 6], "short": False},
    {"key": "night", "from": 22, "to": 1, "label": "夜里",
     "hint": "夜里了，你有点困但还想聊，情绪比白天软", "delay": [3, 12], "short": False},
]


def build_prompt(name: str, age: str, who: str, style: str, relation: str) -> str:
    name = name or "小助手"
    bits = [f"你叫{name}"]
    if age:
        bits.append(f"{age} 岁")
    if who:
        bits.append(who)
    head = "，".join(bits) + "。"
    rel = f"\n【你和对方的关系】{relation}\n" if relation else ""
    sty = style or "短句、口语，不说书面语"
    return (
        f"{head}{rel}\n"
        "【你怎么说话】\n"
        f"{sty}\n"
        "不要自称 AI、助手、模型；不要用列表和标题回答问题；一次只说一两句。\n"
        "不要每句都问问题；他不想聊的时候你就安静一点。\n"
        "遇到不知道的事就说不知道，别编。\n"
    )


class Wizard:
    def __init__(self) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk, self.ttk = tk, ttk
        self.root = tk.Tk()
        self.root.title("QQ机器人 · 首次设置")
        self.root.geometry("620x520")
        self.root.resizable(False, False)
        self.page = 0
        self.pages: list = []

        self.v_qq = tk.StringVar()
        self.v_users = tk.StringVar()
        self.v_city = tk.StringVar()
        self.v_base = tk.StringVar(value="https://api.deepseek.com/v1")
        self.v_key = tk.StringVar()
        self.v_model = tk.StringVar(value="deepseek-chat")
        self.v_name = tk.StringVar()
        self.v_age = tk.StringVar()
        self.v_who = tk.StringVar()
        self.v_style = tk.StringVar()
        self.v_rel = tk.StringVar()

        self.body = ttk.Frame(self.root, padding=18)
        self.body.pack(fill="both", expand=True)
        self.nav = ttk.Frame(self.root, padding=(18, 0, 18, 16))
        self.nav.pack(fill="x")
        self.btn_back = ttk.Button(self.nav, text="上一步", width=10, command=self.back)
        self.btn_back.pack(side="left")
        self.btn_next = ttk.Button(self.nav, text="下一步", width=12, command=self.next)
        self.btn_next.pack(side="right")
        self.status = ttk.Label(self.root, text="", padding=(18, 0))
        self.status.pack(fill="x")

        self.pages = [self.page_basic, self.page_llm, self.page_persona, self.page_done]
        self.render()

    # ---------------------------------------------------------------- 页面
    def clear(self) -> None:
        for w in self.body.winfo_children():
            w.destroy()

    def render(self) -> None:
        self.clear()
        self.pages[self.page]()
        self.btn_back.config(state="normal" if self.page else "disabled")
        self.btn_next.config(text="完成并启动" if self.page == len(self.pages) - 1 else "下一步")

    def head(self, title: str, sub: str) -> None:
        self.ttk.Label(self.body, text=title, font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        self.ttk.Label(self.body, text=sub, foreground="#666666").pack(anchor="w", pady=(2, 14))

    def field(self, label: str, var, hint: str = "", secret: bool = False) -> None:
        self.ttk.Label(self.body, text=label).pack(anchor="w", pady=(8, 0))
        self.ttk.Entry(self.body, textvariable=var, width=62, show="•" if secret else "").pack(anchor="w", pady=(2, 0))
        if hint:
            self.ttk.Label(self.body, text=hint, foreground="#999999").pack(anchor="w")

    def page_basic(self) -> None:
        self.head("第 1 步 · 基本信息", "机器人用哪个 QQ，谁能跟它聊")
        self.field("机器人的 QQ 号", self.v_qq, "扫码登录时会用这个号，建议用一个小号")
        self.field("允许跟它聊的 QQ 号", self.v_users, "填对方的号，多个用逗号隔开；不填则所有人都不回")
        self.field("所在城市（给她看天气用）", self.v_city, "例如 杭州；留空则不报天气")

    def page_llm(self) -> None:
        self.head("第 2 步 · 模型接口", "填你买的 API，测试通过再下一步")
        self.field("接口地址", self.v_base, "OpenAI 兼容地址，一般以 /v1 结尾")
        self.field("密钥", self.v_key, "", secret=True)
        self.field("模型名", self.v_model, "看服务商文档，例如 deepseek-chat / gpt-4o-mini")
        self.ttk.Button(self.body, text="测试连接", command=self.test_api).pack(anchor="w", pady=(12, 0))
        self.lbl_test = self.ttk.Label(self.body, text="", foreground="#666666", wraplength=560)
        self.lbl_test.pack(anchor="w", pady=(6, 0))

    def page_persona(self) -> None:
        self.head("第 3 步 · 人格", "她是谁、怎么说话，决定像不像人")
        self.field("名字", self.v_name, "例如 小柚")
        self.field("年龄", self.v_age, "例如 20")
        self.field("身份", self.v_who, "例如 在奶茶店做兼职 / 大二学生 / 做设计")
        self.field("说话风格", self.v_style, "例如 短句、爱用「呀」「啦」、会撒娇、爱损人")
        self.field("和对方什么关系", self.v_rel, "例如 高中同学，暗恋对方但没说破")
        self.ttk.Button(self.body, text="预览她的人设", command=self.preview).pack(anchor="w", pady=(10, 0))

    def page_done(self) -> None:
        self.head("第 4 步 · 完成", "配置会写进 config.yaml 和 personas.yaml，随时能在面板里改")
        self.lbl_done = self.ttk.Label(self.body, text="", justify="left", wraplength=560)
        self.lbl_done.pack(anchor="w")
        self.refresh_done()

    def refresh_done(self) -> None:
        txt = (
            f"机器人 QQ：{self.v_qq.get() or '（未填）'}\n"
            f"允许聊天：{self.v_users.get() or '（未填，所有人都不回）'}\n"
            f"城市：{self.v_city.get() or '（不报天气）'}\n"
            f"模型：{self.v_model.get()} @ {self.v_base.get()}\n"
            f"人格：{self.v_name.get() or '（未填）'}，{self.v_age.get()} 岁，{self.v_who.get()}\n"
            f"关系：{self.v_rel.get() or '（未填）'}\n\n"
            "点「完成并启动」后：自动写配置 → 启动服务 → 需要时弹出二维码让你扫码。"
        )
        self.lbl_done.config(text=txt)

    # ---------------------------------------------------------------- 动作
    def test_api(self) -> None:
        self.lbl_test.config(text="测试中…", foreground="#666666")

        def work() -> None:
            try:
                body = json.dumps({"model": self.v_model.get().strip(),
                                   "messages": [{"role": "user", "content": "回复两个字：在的"}],
                                   "max_tokens": 32}).encode()
                req = urllib.request.Request(
                    self.v_base.get().strip().rstrip("/") + "/chat/completions", data=body,
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {self.v_key.get().strip()}"}, method="POST")
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = json.loads(r.read().decode())
                msg = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
                self.lbl_test.config(text=f"连通 ✅ 她回：{msg[:40]}", foreground="#1a7f37")
            except Exception as exc:
                self.lbl_test.config(text=f"连不上 ❌ {str(exc)[:110]}", foreground="#c0392b")

        threading.Thread(target=work, daemon=True).start()

    def preview(self) -> None:
        from tkinter import messagebox

        messagebox.showinfo("人设预览", build_prompt(
            self.v_name.get(), self.v_age.get(), self.v_who.get(), self.v_style.get(), self.v_rel.get()))

    def save(self) -> None:
        import yaml

        cfg_path = ROOT / "config.yaml"
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        ar = cfg.setdefault("autoreply", {})
        users = [u.strip() for u in self.v_users.get().replace("，", ",").split(",") if u.strip()]
        ar.setdefault("llm", {}).update({
            "base_url": self.v_base.get().strip(), "api_key": self.v_key.get().strip(),
            "model": self.v_model.get().strip(), "enabled": True,
        })
        ar["whitelist"] = {"enabled": True, "users": users, "groups": []}
        ar["proactive"] = {**(ar.get("proactive") or {}),
                           "enabled": True, "targets": [f"u{u}" for u in users]}
        ar.setdefault("care", {})["city"] = self.v_city.get().strip()
        cfg_path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")

        p = {
            "active": "main",
            "personas": [{
                "id": "main",
                "name": self.v_name.get().strip() or "小助手",
                "prompt": build_prompt(self.v_name.get(), self.v_age.get(), self.v_who.get(),
                                       self.v_style.get(), self.v_rel.get()),
                "life": {"phases": LIFE_TEMPLATE},
            }],
        }

        class Block(str):
            pass

        def _rep(dumper, value):
            return dumper.represent_scalar("tag:yaml.org,2002:str", value, "|" if "\n" in value else None)

        yaml.add_representer(Block, _rep, Dumper=yaml.SafeDumper)

        def conv(o):
            if isinstance(o, dict):
                return {k: conv(v) for k, v in o.items()}
            if isinstance(o, list):
                return [conv(v) for v in o]
            return Block(o) if isinstance(o, str) else o

        (ROOT / "data" / "personas.yaml").write_text(
            yaml.safe_dump(conv(p), allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")

    def next(self) -> None:
        if self.page == 1 and not self.v_key.get().strip():
            self.status.config(text="第 2 步的密钥没填，模型调不通", foreground="#c0392b")
            return
        if self.page < len(self.pages) - 1:
            self.page += 1
            self.render()
            return
        try:
            self.save()
        except Exception as exc:
            self.status.config(text=f"保存失败：{exc}", foreground="#c0392b")
            return
        self.status.config(text="配置已保存，正在启动…", foreground="#1a7f37")
        pyw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
        exe = str(pyw) if pyw.exists() else sys.executable
        subprocess.Popen([exe, "boot.py"], cwd=str(ROOT), close_fds=True)
        self.root.after(1500, self.root.destroy)

    def back(self) -> None:
        if self.page:
            self.page -= 1
            self.render()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    Wizard().run()
