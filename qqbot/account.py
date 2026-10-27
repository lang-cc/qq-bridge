"""机器人 QQ 号从哪儿来。

一份包要能给不同的人装，QQ 号就不能写死在代码里。解析顺序：
    1. 环境变量 BOT_QQ / QQ（部署脚本最常用）
    2. config.yaml 里的 bot_qq / onebot11.account / onebot11.self_id / robot.qq
    3. napcat/config/onebot11_<QQ>.json 的文件名（装完 NapCat 一定会有）
    4. 都没有 → 返回空字符串（调用方自己决定是让用户填还是不带 -q 启动）
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_KEY_PATHS: tuple[tuple[str, ...], ...] = (
    ("bot_qq",),
    ("onebot11", "account"),
    ("onebot11", "self_id"),
    ("robot", "qq"),
)


def _pick(raw: dict, path: tuple[str, ...]) -> str:
    cur: Any = raw
    for part in path:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(part)
    return str(cur or "").strip()


def bot_account(root: str | Path = ".") -> str:
    root = Path(root)

    for key in ("BOT_QQ", "XN_BOT_QQ", "QQ"):
        val = (os.getenv(key) or "").strip()
        if val.isdigit():
            return val

    try:
        from .config import load_config

        raw = load_config(root / "config.yaml").raw
        for path in _KEY_PATHS:
            val = _pick(raw, path)
            if val.isdigit():
                return val
    except Exception:
        pass

    cfgdir = root / "napcat" / "config"
    if cfgdir.is_dir():
        found = sorted(
            m.group(1)
            for m in (re.fullmatch(r"onebot11_(\d+)\.json", p.name) for p in cfgdir.iterdir())
            if m
        )
        if found:
            return found[0]

    return ""


def napcat_launch_args(account: str, *, quiet: bool = True) -> list[str]:
    """给 napcat launcher 拼参数：有号就静默登录指定号，没号就不带 -q。"""
    args: list[str] = []
    if quiet:
        args.append("-q")
    if account:
        args.append(account)
    elif quiet:
        args = []  # 没有号就别硬传 -q（那会当成登录空号）
    return args


def remember_account(root: str | Path, qq: str) -> bool:
    """扫码登录后把真实 QQ 号写回 config.yaml（纯文本替换，不动注释和其他内容）。

    这样装机时不用提前问客户机器人号：扫完码自动记下来，
    下次 boot / watchdog / login_qr 就能静默登录同一个号。
    """
    qq = str(qq or "").strip()
    if not qq.isdigit():
        return False
    path = Path(root) / "config.yaml"
    if not path.exists():
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return False

    hit = False
    out: list[str] = []
    for line in lines:
        if line.startswith("bot_qq:"):
            out.append(f'bot_qq: "{qq}"')
            hit = True
        else:
            out.append(line)
    if not hit:
        out.insert(0, f'bot_qq: "{qq}"')
    try:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    except Exception:
        return False
    return True
