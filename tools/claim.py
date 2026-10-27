"""装完之后的两件小事，一条命令搞定（不用提前问客户 QQ 号）。

1) 认领白名单：扫完码让客户用自己要聊天的 QQ 给机器人发一句话，
   白名单是空的，机器人不会回，但 `logs/qq-bridge.log` 会留下
   `白名单外消息：user=123456 …`。本脚本扫日志，把那个号自动写进白名单，
   再调 `/admin/reload` 热重载 —— 客户再发一句就通了。

2) 记下机器人号：从 `/status` 读 self_id 写进 config.yaml 的 bot_qq，
   以后启动脚本就能静默登录同一个号。

用法：
    python tools/claim.py --status                  # 看当前状态（自检/排查用）
    python tools/claim.py --auto                    # 自动认领：日志里唯一的新号 → 加白名单 → 热重载
    python tools/claim.py --auto --dry-run          # 只看会做什么
    python tools/claim.py --add 123456              # 手动加号（不扫日志）
    python tools/claim.py --set-qq 10001            # 手动写机器人号
    python tools/claim.py --auto --minutes 240      # 只认最近 4 小时的记录
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

USER_RE = re.compile(r"白名单外消息：user=(\d{5,12})")
MAX_BYTES = 4 * 1024 * 1024  # 日志可能很大，只读尾巴


def say(msg: str) -> None:
    print(msg, flush=True)


def read_config(path: Path) -> dict:
    import yaml

    if not path.exists():
        raise SystemExit(f"找不到 {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_config(path: Path, data: dict) -> None:
    import yaml

    header = ""
    if path.exists():
        first = path.read_text(encoding="utf-8").splitlines()[:1]
        if first and first[0].lstrip().startswith("#"):
            header = first[0] + "\n"
    path.write_text(header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")


def tail_text(path: Path, limit: int = MAX_BYTES) -> str:
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - limit))
            return fh.read().decode("utf-8", "ignore")
    except FileNotFoundError:
        return ""


def candidates(roots: list[Path], minutes: int) -> list[tuple[str, int]]:
    """返回 [(qq, 最近出现时间戳)]，按最近出现排序。"""
    cutoff = None if minutes <= 0 else time.time() - minutes * 60
    found: dict[str, int] = {}
    now = int(time.time())
    for log in roots:
        text = tail_text(log)
        for line in text.splitlines():
            m = USER_RE.search(line)
            if not m:
                continue
            stamp = now
            if cutoff is not None:
                # 日志行首是 2026-10-27 11:45:01 这种时间戳，能解析就用它
                head = line[:19]
                try:
                    stamp = int(time.mktime(time.strptime(head, "%Y-%m-%d %H:%M:%S")))
                except Exception:
                    stamp = now
                if stamp < cutoff:
                    continue
            qq = m.group(1)
            found[qq] = max(found.get(qq, 0), stamp)
    return sorted(found.items(), key=lambda kv: kv[1], reverse=True)


def http_json(url: str, data: dict | None = None, timeout: float = 6.0) -> dict:
    body = None
    headers = {}
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers,
                                 method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode() or "{}")


def status(api_port: int) -> dict:
    try:
        return http_json(f"http://127.0.0.1:{api_port}/status")
    except Exception as exc:
        return {"ok": False, "error": repr(exc)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="认领白名单 / 记录机器人号")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--log", action="append", default=None, help="日志路径，可多次给")
    ap.add_argument("--minutes", type=int, default=120, help="只看最近多少分钟（0=不限）")
    ap.add_argument("--auto", action="store_true", help="自动把日志里唯一的新号加进白名单")
    ap.add_argument("--add", action="append", default=None, help="手动加这个 QQ 号（可多次）")
    ap.add_argument("--set-qq", default="", help="写机器人号；填 auto 表示从 /status 取")
    ap.add_argument("--api-port", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-reload", action="store_true", help="不调 /admin/reload")
    args = ap.parse_args(argv)

    cfg_path = Path(args.config)
    cfg = read_config(cfg_path)
    ar = cfg.setdefault("autoreply", {})
    wl = ar.setdefault("whitelist", {})
    users: list[str] = [str(u) for u in (wl.get("users") or [])]
    groups: list[str] = [str(g) for g in (wl.get("groups") or [])]

    api_port = args.api_port
    if api_port is None:
        api_port = int((cfg.get("http_api") or {}).get("port") or 8088)

    logs = [Path(p) for p in args.log] if args.log else [
        ROOT / "logs" / "qq-bridge.log",
        Path.cwd() / "logs" / "qq-bridge.log",
    ]
    logs = list({p.resolve() for p in logs if p.exists()}) or [ROOT / "logs" / "qq-bridge.log"]

    st = status(api_port)
    self_id = str(st.get("self_id") or "")

    changed = False

    # ---- 机器人号 ----
    want_qq = args.set_qq.strip()
    if want_qq == "auto":
        want_qq = self_id
    if want_qq and want_qq.isdigit() and str(cfg.get("bot_qq") or "") != want_qq:
        say(f"· 记录机器人号：{want_qq}")
        cfg["bot_qq"] = want_qq
        changed = True

    # ---- 白名单 ----
    adds: list[str] = []
    for q in (args.add or []):
        q = q.strip()
        if q.isdigit() and q not in users and q not in adds:
            adds.append(q)

    if args.auto:
        cands = candidates(logs, args.minutes)
        cands = [(qq, ts) for qq, ts in cands if qq not in users and qq != (self_id or "0")]
        if not cands:
            say("· 日志里没有发现新的 sender（让客户先给机器人发一句话再来）")
        elif len(cands) == 1:
            adds.append(cands[0][0])
        else:
            say("· 发现多个 sender，无法确定哪个是客户，请用 --add 指定：")
            for qq, ts in cands:
                say(f"    {qq}   最近 {time.strftime('%m-%d %H:%M', time.localtime(ts))}")
            say("  注意：机器人自己的号 %s 不会算进来" % (self_id or "未知"))

    if adds:
        for q in adds:
            say(f"· 加入白名单：{q}")
            users.append(q)
        changed = True

    if not changed:
        say("· 没有需要改动的地方")
    else:
        wl["enabled"] = True
        wl["users"] = users
        wl["groups"] = groups
        if args.dry_run:
            say("· [--dry-run] 未写文件")
        else:
            write_config(cfg_path, cfg)
            say(f"· 已写入 {cfg_path}")

    # ---- 现状 ----
    say("")
    say(f"服务      ：{'在线' if st.get('ok') else '未响应 ' + str(st.get('error', ''))}")
    say(f"机器人号  ：{st.get('self_id') or cfg.get('bot_qq') or '（还没登录）'}")
    say(f"连接状态  ：{st.get('connected')}")
    say(f"白名单    ：{', '.join(users) if users else '（空 —— 谁都不会被回复）'}")
    if groups:
        say(f"群白名单  ：{', '.join(groups)}")

    # ---- 热重载 ----
    if changed and not args.dry_run and not args.no_reload:
        try:
            r = http_json(f"http://127.0.0.1:{api_port}/admin/reload", {})
            say(f"热重载    ：{r}")
        except Exception as exc:
            say(f"热重载失败（手动重启服务即可生效）：{exc!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
