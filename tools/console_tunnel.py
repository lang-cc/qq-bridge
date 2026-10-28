"""给服务器部署开一个控制台隧道（本地 ssh -L），让面板在服务器上也能看。

为什么不用直接暴露 8088：http_api 默认只绑 127.0.0.1（安全默认），把它开到
0.0.0.0 就得同时上 token + 防火墙，交付时容易漏掉一半变成裸奔。走 SSH 隧道
只需要服务器的 SSH 账号，面板天然只有你自己能开，也不占公网端口。

用法：
    python tools/console_tunnel.py --host 47.97.179.152 --user root
    python tools/console_tunnel.py --host 1.2.3.4 --user root --port 22 --password xxx --open

起好后浏览器打开：
    http://127.0.0.1:18088/admin

Ctrl+C 断开。
"""

from __future__ import annotations

import argparse
import select
import socket
import socketserver
import threading
import time
import webbrowser


class _Forward(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def _handler(transport, rhost: str, rport: int):
    class Handler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            try:
                chan = transport.open_channel(
                    "direct-tcpip", (rhost, rport), self.request.getpeername()
                )
            except Exception as exc:  # 服务器没监听 8088 时最常见
                print(f"  隧道建立失败：{exc}")
                return
            if chan is None:
                print("  隧道建立失败：服务器拒绝了 direct-tcpip")
                return
            try:
                while True:
                    r, _, _ = select.select([self.request, chan], [], [])
                    if self.request in r:
                        data = self.request.recv(4096)
                        if not data:
                            break
                        chan.sendall(data)
                    if chan in r:
                        data = chan.recv(4096)
                        if not data:
                            break
                        self.request.sendall(data)
            except Exception:
                pass
            finally:
                try:
                    chan.close()
                except Exception:
                    pass
                self.request.close()

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser(description="把服务器上的 8088 控制台隧道到本地")
    ap.add_argument("--host", required=True, help="服务器 IP / 域名")
    ap.add_argument("--user", default="root", help="SSH 用户（默认 root）")
    ap.add_argument("--port", type=int, default=22, help="SSH 端口（默认 22）")
    ap.add_argument("--password", default="", help="SSH 密码；留空则用密钥/交互")
    ap.add_argument("--remote", default="127.0.0.1:8088", help="服务器上的控制台地址")
    ap.add_argument("--local-port", type=int, default=18088, help="本地端口（默认 18088）")
    ap.add_argument("--open", action="store_true", help="起好后自动打开浏览器")
    args = ap.parse_args()

    try:
        import paramiko
    except ImportError:
        print("缺 paramiko。二选一：")
        print("  pip install paramiko")
        print(f"  或者直接命令行：ssh -N -L {args.local_port}:{args.remote} "
              f"{args.user}@{args.host}")
        return 2

    rhost, _, rport_s = args.remote.partition(":")
    rport = int(rport_s or 8088)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"连接 {args.user}@{args.host}:{args.port} …")
    client.connect(
        args.host,
        port=args.port,
        username=args.user,
        password=args.password or None,
        timeout=15,
        allow_agent=True,
        look_for_keys=True,
    )
    transport = client.get_transport()
    if transport is None:
        print("拿不到 SSH transport，连接失败")
        return 1
    transport.set_keepalive(30)

    server = _Forward(("127.0.0.1", args.local_port), _handler(transport, rhost, rport))
    threading.Thread(target=server.serve_forever, daemon=True).start()

    url = f"http://127.0.0.1:{args.local_port}/admin"
    print(f"隧道已就绪：{url}")
    print(f"（转发 127.0.0.1:{args.local_port} → {args.host}:{args.remote}）")
    print("Ctrl+C 结束。")
    if args.open:
        time.sleep(0.5)
        webbrowser.open(url)
    try:
        while transport.is_active():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n断开。")
    finally:
        server.shutdown()
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
