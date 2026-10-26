"""把 qq-bridge 的反向 WS 写进 NapCat 的配置（不用手点 WebUI）。

用法：
  .venv\\Scripts\\python.exe tools\\setup_napcat.py                # 自动找 napcat/config
  .venv\\Scripts\\python.exe tools\\setup_napcat.py --napcat E:\\dsqq\\napcat --uin 123456

逻辑：在 onebot11_<uin>.json 的 network.websocketClients 里加/更新一条指向
ws://127.0.0.1:8199/onebot/v11/ws 的连接（NapCat 作为客户端主动connect我们）。
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_URL = "ws://127.0.0.1:8199/onebot/v11/ws"
ENTRY_NAME = "qq-bridge"


def find_config_dir(napcat_dir: str) -> str | None:
    for cand in (
        os.path.join(napcat_dir, "napcat", "config"),
        os.path.join(napcat_dir, "config"),
    ):
        if os.path.isdir(cand):
            return cand
    return None


def load_or_new(path: str) -> dict:
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as exc:
            print(f"[!] 读取 {path} 失败，将重建：{exc}")
    return {}


def patch_network(path: str, url: str, token: str) -> bool:
    data = load_or_new(path)
    network = data.setdefault("network", {})
    for key in ("httpServers", "httpSseServers", "httpClients", "websocketServers", "websocketClients"):
        network.setdefault(key, [])

    entry = {
        "enable": True,
        "name": ENTRY_NAME,
        "url": url,
        "reportSelfMessage": False,
        "messagePostFormat": "array",
        "token": token,
        "debug": False,
        "heartInterval": 30000,
        "reconnectInterval": 5000,
    }
    clients = network["websocketClients"]
    for i, item in enumerate(clients):
        if isinstance(item, dict) and item.get("name") == ENTRY_NAME:
            clients[i] = {**item, **entry}
            break
    else:
        clients.append(entry)

    data.setdefault("musicSignUrl", "")
    data.setdefault("enableLocalFile2Url", False)
    data.setdefault("parseMultMsg", False)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--napcat", default=os.path.join(ROOT, "napcat"), help="NapCat 解压目录")
    ap.add_argument("--uin", help="机器人 QQ 号（不填就按已有的配置文件名猜）")
    ap.add_argument("--url", default=DEFAULT_URL, help="反向 WS 地址")
    ap.add_argument("--token", default="", help="和 config.yaml 里 onebot11.access_token 保持一致")
    args = ap.parse_args()

    cfg_dir = find_config_dir(args.napcat)
    if not cfg_dir:
        print(f"[!] 没找到 NapCat 配置目录，先启动一次 NapCat 让它生成：{args.napcat}\\napcat\\config")
        return 1

    if args.uin:
        targets = [os.path.join(cfg_dir, f"onebot11_{args.uin}.json")]
    else:
        targets = glob.glob(os.path.join(cfg_dir, "onebot11_*.json"))

    if not targets:
        uin = args.uin or input("还没登录过，先输入机器人 QQ 号用于生成配置：").strip()
        targets = [os.path.join(cfg_dir, f"onebot11_{uin}.json")]

    for path in targets:
        patch_network(path, args.url, args.token)
        print(f"[OK] 已写入：{path} -> {args.url}")

    # WebUI token 提示
    webui = os.path.join(cfg_dir, "webui.json")
    if os.path.isfile(webui):
        try:
            with open(webui, "r", encoding="utf-8") as f:
                w = json.load(f)
            print(f"[i] NapCat WebUI: http://127.0.0.1:{w.get('port', 6099)}/webui?token={w.get('token', '')}")
        except Exception:
            pass

    print("\n下一步：重启 NapCat，然后 `.venv\\Scripts\\python.exe main.py`，")
    print("日志出现「协议端已连上反向 WS」就成了。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
