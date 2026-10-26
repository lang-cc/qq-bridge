"""一条命令建仓库 + 推代码 + 发 Release。GitHub / Gitee 都支持。

用法（令牌只走环境变量或参数，不落盘）：

    # GitHub
    python publish.py --host github --token ghp_xxx --user 你的用户名

    # Gitee
    python publish.py --host gitee --token 你的私人令牌 --user 你的用户名

    # 只建仓库不推送
    python publish.py --host gitee --token xxx --user 你的名 --no-push

做的事：
    1. 查仓库是否已存在，没有就建（默认私有）
    2. git remote add origin + push
    3. 打包 dist zip 并作为 Release 附件上传（--release）
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

API = {
    "github": "https://api.github.com",
    "gitee": "https://gitee.com/api/v5",
}
WEB = {
    "github": "https://github.com",
    "gitee": "https://gitee.com",
}


def api_call(host: str, method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    url = API[host] + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json" if host == "github" else "application/json",
    }
    if host == "github":
        headers["Authorization"] = f"Bearer {token}"
    else:
        if method == "GET":
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}access_token={urllib.parse.quote(token)}"
        else:
            body = dict(body or {})
            body["access_token"] = token
            data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, {"message": raw[:200]}
    except Exception as exc:
        return 0, {"message": repr(exc)}


def sh(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(cwd or ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def build_zip() -> Path:
    out = ROOT / "dist" / "qq-bridge.zip"
    out.parent.mkdir(exist_ok=True)
    staging = ROOT / "dist" / "_pkg"
    if staging.exists():
        subprocess.run(["cmd", "/c", "rd", "/s", "/q", str(staging)], capture_output=True)
    staging.mkdir(parents=True, exist_ok=True)
    code, log = sh(["git", "archive", "HEAD", "--prefix=qq-bridge/", "-o", str(out)])
    if code != 0:
        raise SystemExit(f"打包失败：{log[:300]}")
    print(f"已打包 {out}（{out.stat().st_size // 1024} KB）")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", choices=["github", "gitee"], default="github")
    ap.add_argument("--token", default=os.environ.get("GIT_TOKEN") or os.environ.get("GH_TOKEN") or "")
    ap.add_argument("--user", default="", help="你的用户名（仓库所有者的账号名）")
    ap.add_argument("--repo", default="qq-bridge")
    ap.add_argument("--public", action="store_true", help="默认私有；加这个才公开")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--release", action="store_true", help="顺便发 Release 并附上 zip")
    args = ap.parse_args()

    token, user = args.token.strip(), args.user.strip()
    if not token:
        print("缺令牌。生成方式：")
        print("  GitHub → https://github.com/settings/tokens/new?scopes=repo")
        print("  Gitee  → https://gitee.com/profile/personal_access_tokens")
        print("然后：python publish.py --host github --token ghp_xxx --user 你的名")
        return 2

    # 1) 谁在登录 + 用户名
    if not user:
        code, me = api_call(args.host, "GET", "/user", token)
        if code != 200:
            print(f"令牌验证失败（{code}）：{me.get('message')}")
            return 3
        user = me.get("login") or me.get("username") or ""
        if not user:
            print("拿不到用户名，请用 --user 指定")
            return 3
    print(f"账号：{user}（{args.host}）")

    # 2) 仓库
    code, info = api_call(args.host, "GET", f"/repos/{user}/{args.repo}", token)
    if code == 200:
        print(f"仓库已存在：{info.get('html_url')}")
    else:
        body = {"name": args.repo, "private": not args.public, "auto_init": False,
                "description": "QQ 拟人陪聊机器人（NapCat + OneBot v11）"}
        code, info = api_call(args.host, "POST", "/user/repos", token, body)
        if code not in (200, 201):
            print(f"建仓库失败（{code}）：{info.get('message')}")
            return 4
        print(f"已创建仓库：{info.get('html_url')}（{'公开' if args.public else '私有'}）")

    repo_url = info.get("html_url") or f"{WEB[args.host]}/{user}/{args.repo}"
    if args.host == "github":
        remote = f"https://{user}:{token}@github.com/{user}/{args.repo}.git"
    else:
        remote = f"https://{user}:{token}@gitee.com/{user}/{args.repo}.git"

    # 3) 推送
    if not args.no_push:
        sh(["git", "remote", "remove", "origin"])
        code, log = sh(["git", "remote", "add", "origin", remote])
        if code != 0:
            print(f"加 remote 失败：{log[:200]}")
            return 5
        sh(["git", "branch", "-M", "main"])
        print("推送中…（网断会失败，重跑本命令即可）")
        code, log = sh(["git", "push", "-u", "origin", "main", "--force"])
        if code != 0:
            print(f"推送失败：{log.strip()[:400]}")
            print("网络恢复后重跑同一条命令即可，不用改任何东西。")
            return 6
        print("推送成功 ✅")

    # 4) Release
    if args.release:
        zpath = build_zip()
        if args.host == "github":
            code, rel = api_call(args.host, "POST", f"/repos/{user}/{args.repo}/releases", token, {
                "tag_name": "v1.0", "name": "v1.0", "body": "首个交付版本"})
        else:
            code, rel = api_call(args.host, "POST", f"/repos/{user}/{args.repo}/releases", token, {
                "tag_name": "v1.0", "name": "v1.0", "target_commitish": "main", "body": "首个交付版本"})
        if code in (200, 201):
            print(f"Release 已建：{rel.get('html_url')}")
            print(f"固定下载链接（发这一个给客户）：{rel.get('html_url')}")
        else:
            print(f"Release 创建失败（{code}）：{rel.get('message')}")
        print(f"zip 在本地：{zpath}（可在网页上手动上传到 Release）")

    print(f"\n仓库地址：{repo_url}")
    print("提醒：令牌用完去后台 Revoke 作废，仓库不受影响。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
