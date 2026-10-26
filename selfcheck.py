"""交付自检：一条命令查完 12 项，出人话报告。

用法：
    python selfcheck.py            # 控制台报告
    python selfcheck.py --json     # 机器可读

给客服/客户用：跑完看到「全部通过」就可以交付了。
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = "http://127.0.0.1:8088"


def port(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) == 0


def get(path: str) -> dict:
    try:
        with urllib.request.urlopen(API + path, timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {}


def post(path: str, body: dict) -> dict:
    try:
        req = urllib.request.Request(API + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {}


def check() -> list[dict]:
    import yaml

    out: list[dict] = []

    def add(name: str, ok: bool, detail: str = "", tip: str = "") -> None:
        out.append({"name": name, "ok": bool(ok), "detail": detail, "tip": tip})

    # 1 Python
    add("Python 版本", sys.version_info >= (3, 10), sys.version.split()[0], "需要 3.10 以上")
    # 2 依赖
    missing = []
    for m in ("aiohttp", "websockets", "yaml"):
        try:
            __import__(m)
        except Exception:
            missing.append(m)
    add("Python 依赖", not missing, "缺失: " + ",".join(missing) if missing else "齐全",
        "pip install -r requirements.txt")
    # 3 配置可读
    cfg = {}
    try:
        cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")) or {}
        add("配置文件", True, "config.yaml 可读")
    except Exception as exc:
        add("配置文件", False, repr(exc)[:60], "检查 config.yaml 格式")
    ar = (cfg.get("autoreply") or {})
    # 4 API 配置
    llm = ar.get("llm") or {}
    add("模型接口", bool(llm.get("base_url") and llm.get("api_key") and llm.get("model")),
        f"{llm.get('base_url','(空)')} / {llm.get('model','(空)')}", "面板 →「模型设置」填 API")
    # 5 模型连通
    if llm.get("base_url"):
        try:
            body = json.dumps({"model": llm.get("model"), "messages": [{"role": "user", "content": "在"}],
                               "max_tokens": 8}).encode()
            req = urllib.request.Request(llm["base_url"].rstrip("/") + "/chat/completions", data=body,
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": f"Bearer {llm.get('api_key','')}"}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as r:
                json.loads(r.read().decode())
            add("模型连通", True, "调用成功")
        except Exception as exc:
            add("模型连通", False, str(exc)[:70], "换接口地址/密钥，或检查网络能否访问该域名")
    # 6 人格
    try:
        pdata = yaml.safe_load((ROOT / "data" / "personas.yaml").read_text(encoding="utf-8")) or {}
        ps = pdata.get("personas") or []
        active = pdata.get("active")
        cur = next((p for p in ps if p.get("id") == active), None)
        add("人格", bool(cur and (cur.get("prompt") or "").strip()),
            f"{len(ps)} 个人格，当前 {(cur or {}).get('name') or '(无)'}", "data/personas.yaml 里写 prompt")
    except Exception as exc:
        add("人格", False, repr(exc)[:60], "检查 personas.yaml")
    # 7 服务
    st = get("/status")
    add("服务运行", bool(st.get("ok")), "http 接口在线" if st.get("ok") else "8088 未响应",
        "双击桌面图标 → 启动")
    # 8 QQ 连接
    add("QQ 已连接", bool(st.get("connected")), f"账号 {st.get('self_id') or '(未登录)'}",
        "面板 →「扫码登录」")
    # 9 白名单
    wl = ar.get("whitelist") or {}
    users = [u for u in (wl.get("users") or []) if str(u).strip()]
    add("白名单", bool(users), f"{len(users)} 个 QQ：{', '.join(map(str, users[:3]))}",
        "没填白名单则所有人都不回")
    # 10 记忆库
    mem = ROOT / "data" / "personas"
    dbs = list(mem.glob("*/memory.db"))
    add("记忆库", bool(dbs), f"{len(dbs)} 个库", "首次聊天后自动创建")
    # 11 看门狗
    add("掉线监控", port(9335), "运行中" if port(9335) else "未运行",
        "面板 →「自动修复」，建议常开")
    # 12 NapCat
    add("NapCat", port(6099), "WebUI 在线" if port(6099) else "未运行", "看 napcat 目录是否完整")
    return out


def main() -> int:
    items = check()
    if "--json" in sys.argv:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print("=" * 46)
        print("  QQ机器人 交付自检")
        print("=" * 46)
        for it in items:
            mark = "✅" if it["ok"] else "❌"
            print(f"{mark} {it['name']:<10} {it['detail']}")
            if not it["ok"] and it["tip"]:
                print(f"     ↳ 处理：{it['tip']}")
        bad = [i for i in items if not i["ok"]]
        print("-" * 46)
        print(f"通过 {len(items) - len(bad)}/{len(items)}")
        print("结论：" + ("全部通过，可以交付 ✅" if not bad else "还有问题需要处理 ❌"))
    return 0 if all(i["ok"] for i in items) else 1


if __name__ == "__main__":
    raise SystemExit(main())
