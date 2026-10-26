"""命令行发送工具：不写代码也能让机器人主动发消息。

示例：
  .venv\\Scripts\\python.exe tools\\cli.py status
  .venv\\Scripts\\python.exe tools\\cli.py text   --group 123456 --text "上线了"
  .venv\\Scripts\\python.exe tools\\cli.py image  --user 654321 --src E:/pics/1.png
  .venv\\Scripts\\python.exe tools\\cli.py voice  --group 123456 --src E:/audio/1.silk
  .venv\\Scripts\\python.exe tools\\cli.py link   --group 123456 --url https://example.com --title 示例
  .venv\\Scripts\\python.exe tools\\cli.py screen --group 123456
  .venv\\Scripts\\python.exe tools\\cli.py screen --group 123456 --url https://example.com
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="qq-bridge 发送工具")
    p.add_argument("--base", default="http://127.0.0.1:8088", help="发送接口地址")
    p.add_argument("--token", default="", help="接口 token（配置里填了才需要）")
    sub = p.add_subparsers(dest="cmd", required=True)

    def target(sp: argparse.ArgumentParser) -> None:
        g = sp.add_mutually_exclusive_group(required=True)
        g.add_argument("--group", type=int, help="群号")
        g.add_argument("--user", type=int, help="QQ 号（私聊）")

    sub.add_parser("status", help="查看连接状态")

    sp = sub.add_parser("text", help="发文字"); target(sp)
    sp.add_argument("--text", required=True); sp.add_argument("--at", help="额外 @ 某人")

    sp = sub.add_parser("image", help="发图片"); target(sp)
    sp.add_argument("--src", required=True, help="本地路径 / http URL / base64://")

    sp = sub.add_parser("voice", help="发语音"); target(sp)
    sp.add_argument("--src", required=True, help="音频路径（silk）")

    sp = sub.add_parser("video", help="发视频"); target(sp)
    sp.add_argument("--src", required=True)

    sp = sub.add_parser("file", help="发文件"); target(sp)
    sp.add_argument("--src", required=True); sp.add_argument("--name")

    sp = sub.add_parser("link", help="发链接卡片"); target(sp)
    sp.add_argument("--url", required=True); sp.add_argument("--title", default="")
    sp.add_argument("--desc", default=""); sp.add_argument("--preview", default="")

    sp = sub.add_parser("screen", help="截屏发送"); target(sp)
    sp.add_argument("--url", help="截网页；不填则截本机桌面")

    sp = sub.add_parser("raw", help="直接发 message 数组 JSON"); target(sp)
    sp.add_argument("--json", required=True, help='例如 [{"type":"text","data":{"text":"hi"}}]')

    return p


ENDPOINT = {
    "text": "/send/text",
    "image": "/send/image",
    "voice": "/send/voice",
    "video": "/send/video",
    "file": "/send/file",
    "link": "/send/link",
    "screen": "/send/screenshot",
    "raw": "/send",
}


def main() -> int:
    args = build_parser().parse_args()
    url = args.base.rstrip("/") + ("/status" if args.cmd == "status" else ENDPOINT[args.cmd])

    body: dict = {}
    if args.cmd != "status":
        if getattr(args, "group", None):
            body["group_id"] = args.group
        if getattr(args, "user", None):
            body["user_id"] = args.user
        if args.cmd == "text":
            body["text"] = args.text
            if args.at:
                body["at"] = args.at
        elif args.cmd in ("image", "voice", "video", "file"):
            body["src"] = args.src
            if getattr(args, "name", None):
                body["name"] = args.name
        elif args.cmd == "link":
            body.update(url=args.url, title=args.title, desc=args.desc, preview=args.preview)
        elif args.cmd == "screen":
            if args.url:
                body["url"] = args.url
        elif args.cmd == "raw":
            body["message"] = json.loads(args.json)

    if args.cmd == "status":
        req = urllib.request.Request(url, method="GET")
    else:
        data = json.dumps(body, ensure_ascii=False).encode()
        req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    if args.token:
        req.add_header("X-Token", args.token)

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(r.read().decode())
            return 0
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"连不上发送接口 {url}：{e.reason}（服务起了吗？）", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
