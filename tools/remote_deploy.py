"""远程部署：通过 SSH-over-443 在客户服务器上跑 deploy-linux.sh。

用法：
    python tools/remote_deploy.py --host 47.97.179.152 --port 443 --user root --password xxx \
        --script scripts/deploy-linux.sh --env-file tmp/remote.env
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import paramiko


def run(client, cmd: str, timeout: int = 1800, log=print) -> int:
    """执行命令并实时打印输出。"""
    chan = client.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    while True:
        if chan.recv_ready():
            data = chan.recv(65536).decode("utf-8", "replace")
            log(data, end="")
        if chan.exit_status_ready() and not chan.recv_ready():
            while chan.recv_ready():
                log(chan.recv(65536).decode("utf-8", "replace"), end="")
            break
        time.sleep(0.2)
    return chan.recv_exit_status()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, default=443)
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", required=True)
    ap.add_argument("--script", default="scripts/deploy-linux.sh")
    ap.add_argument("--env-file", default="")
    ap.add_argument("--timeout", type=int, default=2400)
    args = ap.parse_args()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"连接 {args.host}:{args.port} …")
    client.connect(args.host, port=args.port, username=args.user,
                   password=args.password, timeout=25, banner_timeout=25,
                   auth_timeout=25, look_for_keys=False, allow_agent=False)
    print("已登录\n")

    # 环境变量（从 env 文件读，一行一个 KEY=VALUE）
    env_lines = []
    if args.env_file and Path(args.env_file).exists():
        for line in Path(args.env_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                env_lines.append(line)
    env_prefix = " \\\n  ".join(env_lines)

    print("--- 清理临时进程 / 停旧服务 ---")
    run(client, "pkill -f 'http.server 6099' 2>/dev/null; pkill -f '/opt/qqbridge/main.py' 2>/dev/null; sleep 1; echo done")

    print("\n--- 上传部署脚本 ---")
    sftp = client.open_sftp()
    with sftp.file("/tmp/deploy-linux.sh", "w") as fh:
        fh.write(Path(args.script).read_text(encoding="utf-8"))
    sftp.chmod("/tmp/deploy-linux.sh", 0o755)
    sftp.close()
    run(client, "chmod +x /tmp/deploy-linux.sh && wc -c /tmp/deploy-linux.sh")

    print("\n--- 开始部署（5-10 分钟，实时输出）---")
    cmd = f"cd /root && {env_prefix} bash /tmp/deploy-linux.sh 2>&1"
    code = run(client, cmd, timeout=args.timeout)
    print(f"\n--- 部署脚本退出码：{code} ---")

    print("\n--- 收尾检查 ---")
    run(client, "free -h; echo; docker ps --format '{{.Names}} {{.Status}}'; echo; "
                "curl -s http://127.0.0.1:8088/status || echo '(状态接口未就绪)'")

    client.close()
    print("\n完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
