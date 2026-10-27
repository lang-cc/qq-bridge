"""打包脚本：把当前目录打成可对外分发的 zip（不含密钥 / 数据 / 日志 / 虚拟环境）。

用法：
    python tools/make_dist.py                       # 只打代码包（几百 KB）
    python tools/make_dist.py --with-assets         # 附带表情包（26MB）和示例素材
    python tools/make_dist.py --with-napcat         # 附带 NapCat.Shell.zip（35MB）
    python tools/make_dist.py --all                 # 一次打两个：code + full

产物：
    dist/qq-bridge-code-<版本>.zip   代码包（Linux 一键部署拉的就是它）
    dist/qq-bridge-full-<版本>.zip   完整包（代码 + 表情包 + NapCat，给 Windows 客户机）

安全：config.yaml / nb.env / data/ / logs/ / tmp/ / ticket.yaml / .venv / .git 一律不进包。
"""

from __future__ import annotations

import argparse
import fnmatch
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 整个目录都收
DIRS = [
    "nb",
    "qqbot",
    "scripts",
    "static",
    "docs",
    "tests",
    "assets",
]

# 单文件收（存在才收）
FILES = [
    "main_nb.py",
    "main.py",
    "boot.py",
    "watchdog.py",
    "login_qr.py",
    "selfcheck.py",
    "autoconfig.py",
    "setup_wizard.py",
    "deploy.ps1",
    "install.ps1",
    "deploy-aliyun.ps1",
    "requirements.txt",
    "config.example.yaml",
    "personas.example.yaml",
    "ticket.example.yaml",
    "nb.env.example",
    "README.md",
    "LICENSE",
    "安装.bat",
    "run.bat",
    "start_all.bat",
    "stop_all.bat",
    "start_silent.vbs",
    "open_console.vbs",
    "交付说明.md",
    "交付说明-小念.md",
]

# tools/ 里只收代码，不收 ffmpeg / 下载缓存 / node_modules
TOOLS_KEEP = ["*.py", "*.md", "*.sh"]

# 永远不进包
DENY_NAMES = [
    "config.yaml",
    "nb.env",
    "ticket.yaml",
    "*.bak",
    "*.pyc",
    ".gitignore",
]
DENY_DIRS = [
    "__pycache__",
    ".git",
    ".venv",
    ".venv-*",
    ".cache",
    ".dsh-pyenv",
    "data",
    "logs",
    "tmp",
    "dist",
    "napcat",
    "node_modules",
    "backups",
    ".pytest_cache",
    "browser-*",
]
DENY_EXT = [".pyc", ".db", ".db-wal", ".db-shm", ".log", ".zip", ".mp3", ".silk", ".pcm"]


def denied(path: Path) -> bool:
    name = path.name
    for pat in DENY_NAMES:
        if fnmatch.fnmatch(name, pat):
            return True
    for part in path.parts:
        for pat in DENY_DIRS:
            if fnmatch.fnmatch(part, pat):
                return True
    if path.suffix.lower() in DENY_EXT:
        return True
    return False


def iter_files(with_assets: bool, with_stickers: bool):
    for d in DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or denied(p.relative_to(ROOT)):
                continue
            yield p
    for f in FILES:
        p = ROOT / f
        if p.is_file() and not denied(p):
            yield p
    tdir = ROOT / "tools"
    if tdir.is_dir():
        for p in sorted(tdir.rglob("*")):
            if not p.is_file() or denied(p.relative_to(ROOT)):
                continue
            if any(fnmatch.fnmatch(p.name, pat) for pat in TOOLS_KEEP):
                yield p
    if with_assets or with_stickers:
        sdir = ROOT / "stickers"
        if sdir.is_dir():
            for p in sorted(sdir.rglob("*")):
                if p.is_file() and not denied(p.relative_to(ROOT)):
                    # 表情包里的图片不能被 DENY_EXT 拦掉，这里单独放行
                    if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
                        yield p


def build(out: Path, files: list[Path], extras: list[Path] | None = None) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in files:
            arc = p.relative_to(ROOT).as_posix()
            if arc in seen:
                continue
            seen.add(arc)
            zf.write(p, arc)
        for p in extras or []:
            arc = p.name
            if arc in seen:
                continue
            seen.add(arc)
            zf.write(p, arc)
    size = out.stat().st_size / 1024 / 1024
    print(f"  → {out}  （{len(seen)} 个文件，{size:.1f} MB）")
    return out


def check_ps1_bom(files: list[Path]) -> list[Path]:
    """Windows PowerShell 5.1 用 ANSI 读 .ps1，没有 UTF-8 BOM 会把中文和引号读崩。

    打包前检查一遍，缺 BOM 的自动补上（改完文件记得再跑一次打包）。
    """
    fixed: list[Path] = []
    for p in files:
        if p.suffix.lower() != ".ps1" or not p.is_file():
            continue
        data = p.read_bytes()
        if not data.startswith(b"\xef\xbb\xbf"):
            p.write_bytes(b"\xef\xbb\xbf" + data)
            fixed.append(p)
    return fixed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="打可分发的 zip 包")
    ap.add_argument("--out", default="dist", help="输出目录（默认 dist）")
    ap.add_argument("--version", default=datetime.now().strftime("%Y%m%d"), help="版本号，进文件名")
    ap.add_argument("--with-assets", action="store_true", help="带上表情包 stickers/")
    ap.add_argument("--with-napcat", action="store_true", help="带上 NapCat.Shell.zip")
    ap.add_argument("--all", action="store_true", help="同时打 code 包和 full 包")
    args = ap.parse_args(argv)

    outdir = (ROOT / args.out).resolve()
    code_files = list(iter_files(with_assets=False, with_stickers=False))

    fixed = check_ps1_bom(code_files)
    if fixed:
        print("  已给这些 .ps1 补上 UTF-8 BOM：" + "、".join(p.name for p in fixed))

    napcat_zip = None
    for cand in (ROOT / "NapCat.Shell.zip", ROOT / "tmp" / "NapCat.Shell.zip"):
        if cand.is_file():
            napcat_zip = cand
            break

    print("打包中…")
    made: list[Path] = []
    if args.all or not (args.with_assets or args.with_napcat):
        made.append(build(outdir / f"qq-bridge-code-{args.version}.zip", code_files))

    if args.all or args.with_assets or args.with_napcat:
        extra_files = list(iter_files(with_assets=args.with_assets, with_stickers=args.with_assets))
        extras: list[Path] = []
        if args.with_napcat:
            if napcat_zip is None:
                print("  ! 没找到 NapCat.Shell.zip（放根目录或 tmp/ 里），full 包将不含协议端")
            else:
                extras.append(napcat_zip)
        made.append(build(outdir / f"qq-bridge-full-{args.version}.zip", extra_files, extras))

    # 再放一份固定名字的副本：gitee 发行版里的下载直链就不会随版本变
    for p in made:
        stable = p.with_name("qq-bridge-code.zip" if "-code-" in p.name else "qq-bridge-full.zip")
        stable.write_bytes(p.read_bytes())
        print(f"  → {stable}  （固定名，部署脚本默认拉这个）")

    print("\n完成。注意：包里没有 config.yaml / nb.env / 记忆库，装完由脚本生成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
