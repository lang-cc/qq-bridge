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
