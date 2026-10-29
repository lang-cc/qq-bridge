"""版本信息：控制台顶栏那行「v0.1.0 · main@88820a2 · 更新于 10-29 09:30」。

客户的机器上通常没有装 git，所以这里不调用 git 命令，按三个来源依次读：
1. VERSION.txt —— 更新脚本（scripts/update.ps1）和打包脚本（tools/make_dist.py）写的，
   带明确的更新时间和来源，最可信；
2. .git —— 直接读 .git/HEAD 和 refs，再把 commit 对象解压出来取日期；
3. 兜底 —— 用 qqbot/__init__.py 的修改时间。

目的只有一个：更新完能一眼看出「到底变成新版了没」，不用靠猜。
"""

from __future__ import annotations

import time
import zlib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION.txt"


def _pkg_version() -> str:
    try:
        from . import __version__ as v

        return str(v or "").strip() or "0.0.0"
    except Exception:
        return "0.0.0"


def _read_version_file() -> dict[str, str]:
    """VERSION.txt 是简单的 key=value，一行一个；读不了就当没有。"""
    out: dict[str, str] = {}
    try:
        for line in VERSION_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip().lower()] = v.strip()
    except OSError:
        return {}
    return out


def _git_dir() -> Path | None:
    dot = ROOT / ".git"
    if dot.is_dir():
        return dot
    try:  # worktree / 子模块：.git 是个文件，内容形如 "gitdir: /path/to/xxx"
        if dot.is_file():
            txt = dot.read_text(encoding="utf-8", errors="replace").strip()
            if txt.lower().startswith("gitdir:"):
                p = Path(txt.split(":", 1)[1].strip())
                return p if p.is_absolute() else (ROOT / p).resolve()
    except OSError:
        pass
    return None


def _git_head_sha(git: Path) -> str:
    head = (git / "HEAD").read_text(encoding="utf-8", errors="replace").strip()
    if not head.lower().startswith("ref:"):
        return head  # 分离头指针，HEAD 里直接就是 sha
    ref = head.split(":", 1)[1].strip()
    ref_file = git / ref
    if ref_file.is_file():
        return ref_file.read_text(encoding="utf-8", errors="replace").strip()
    packed = git / "packed-refs"  # 被 gc 打包过的 ref
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "^")):
                continue
            parts = line.split(" ", 1)
            if len(parts) == 2 and parts[1].strip() == ref:
                return parts[0].strip()
    return ""


def _commit_time(git: Path, sha: str) -> float:
    """从 .git/objects 里把 commit 对象解压出来，取 committer 那一行的时间戳。"""
    if len(sha) < 4:
        return 0.0
    obj = git / "objects" / sha[:2] / sha[2:]
    try:
        raw = zlib.decompress(obj.read_bytes())
    except (OSError, zlib.error):
        return 0.0  # 没打包进对象库（稀疏/shallow 克隆）就算不出来，不影响使用
    try:
        for line in raw.split(b"\n"):
            if line.startswith(b"committer "):
                tail = line.rsplit(b" ", 2)  # ... <邮箱> <时间戳> <时区>
                return float(tail[-2])
            if not line.strip():
                break  # 到空行就是提交信息了，committer 一定在前面
    except (ValueError, IndexError):
        pass
    return 0.0


def _fmt_ts(ts: float) -> str:
    if not ts or ts <= 0:
        return ""
    return time.strftime("%m-%d %H:%M", time.localtime(ts))


def info() -> dict[str, Any]:
    """给页面和 /status 用的版本快照。"""
    ver = _pkg_version()
    out: dict[str, Any] = {
        "version": ver,
        "commit": "",
        "ref": "",
        "source": "",
        "updated_at": "",
        "time": "",
        "label": f"v{ver}",
    }

    vf = _read_version_file()
    if vf.get("version"):
        out["version"] = vf["version"]
    out["ref"] = vf.get("ref", "")
    out["source"] = vf.get("source", "")
    out["updated_at"] = vf.get("updated_at", "")

    git = _git_dir()
    if git is not None:
        try:
            sha = _git_head_sha(git)
            if sha:
                out["commit"] = sha[:7]
                ts = _commit_time(git, sha)
                if ts:
                    out["commit_date"] = _fmt_ts(ts)
        except OSError:
            pass

    if not out["time"]:
        out["time"] = out["updated_at"] or out.get("commit_date", "")

    if not out["updated_at"] and not out["commit"]:
        try:  # 既没有 VERSION.txt 也没有 .git：至少让人知道这份代码是什么时候落的盘
            out["time"] = _fmt_ts((ROOT / "qqbot" / "__init__.py").stat().st_mtime)
            out["source"] = out["source"] or "本地打包"
        except OSError:
            pass

    bits = [f"v{out['version']}"]
    if out["commit"]:
        bits.append(f"{out['ref'] or 'main'}@{out['commit']}")
    if out["time"]:
        bits.append(f"更新于 {out['time']}")
    out["label"] = " · ".join(bits)
    return out
