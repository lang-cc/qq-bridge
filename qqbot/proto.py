"""协议端后端：NapCat ↔ SnowLuma。

两个后端都跑在本机 127.0.0.1、都吐 OneBot v11，所以业务层（qqbot.*）不用管是谁。
需要区分的地方集中在三处，原来散在 boot.py / watchdog.py / login_qr.py 里，现在收这里：

    |          | NapCat                        | SnowLuma                              |
    |----------|-------------------------------|---------------------------------------|
    | WebUI    | 6099                          | 5099                                  |
    | 启动     | napcat/launcher-user-silent.bat | snowluma/node.exe snowluma/index.mjs |
    | 登录     | -q <QQ> 静默登录 / 登录页扫码   | 只能在自己弹出来的 QQ 窗口里扫码      |
    | 注入方式 | 自己引导 QQ 启动               | 注入已在跑的 QQ.exe（hookAutoLoad）    |

切换方式：config.yaml 里 `protocol_backend: napcat | snowluma`，
环境变量 QQ_BACKEND 优先级更高（临时试一下不用改文件）。
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

BACKENDS = ("napcat", "snowluma")
WEBUI_PORT = {"napcat": 6099, "snowluma": 5099}
ACTION_PORT = 3000

_QQ_CANDIDATES = (
    r"C:\Program Files\Tencent\QQNT\QQ.exe",
    r"C:\Program Files (x86)\Tencent\QQNT\QQ.exe",
    r"C:\Program Files\Tencent\QQ\QQ.exe",
)


# ---------------------------------------------------------------- 基础工具
def root_of(root: str | Path | None = None) -> Path:
    return Path(root).resolve() if root else Path(__file__).resolve().parent.parent


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.4) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def _no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


def _read_config(root: Path) -> dict:
    try:
        from .config import load_config

        return load_config(root / "config.yaml").raw or {}
    except Exception:
        return {}


# ---------------------------------------------------------------- 选哪个后端
def backend(root: str | Path | None = None) -> str:
    """环境变量 QQ_BACKEND > config.yaml 的 protocol_backend > napcat。"""
    env = (os.getenv("QQ_BACKEND") or os.getenv("XN_BACKEND") or "").strip().lower()
    if env in BACKENDS:
        return env
    name = str(_read_config(root_of(root)).get("protocol_backend") or "").strip().lower()
    return name if name in BACKENDS else "napcat"


def webui_port(name: str | None = None) -> int:
    return WEBUI_PORT.get(name or backend(), WEBUI_PORT["napcat"])


def action_port() -> int:
    return ACTION_PORT


def webui_url(root: str | Path | None = None, name: str | None = None) -> str:
    """浏览器打开的面板地址（NapCat 需要带 token 参数，SnowLuma 用登录密码）。"""
    name = name or backend(root)
    port = webui_port(name)
    if name == "napcat":
        token = napcat_webui_token(root)
        return f"http://127.0.0.1:{port}/webui/?token={token}" if token else f"http://127.0.0.1:{port}/webui/"
    return f"http://127.0.0.1:{port}/"


# ---------------------------------------------------------------- 状态探测
def is_up(root: str | Path | None = None, name: str | None = None) -> bool:
    """协议端进程活着没（看 WebUI 端口）。"""
    return port_open(webui_port(name or backend(root)))


def supports_quick_login(name: str | None = None) -> bool:
    """NapCat 能 -q <QQ> 静默登录；SnowLuma 只能扫码。"""
    return (name or backend()) == "napcat"


def online() -> bool:
    """QQ 真的上线了没：协议端的 OneBot HTTP（3000）起来了才算。"""
    return port_open(ACTION_PORT)


def napcat_webui_token(root: str | Path | None = None) -> str:
    p = root_of(root) / "napcat" / "config" / "webui.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("token", "") or ""
    except Exception:
        return ""


# ---------------------------------------------------------------- 进程操作
def qq_running() -> bool:
    """QQ 在不在跑。探测失败按「没跑」处理：重复拉起 QQ 只会激活窗口，不会出事，
    而漏拉起会让人对着空屏幕等一个永远不出现的二维码。"""
    if sys.platform != "win32":
        return True
    try:
        out = subprocess.run(
            ["tasklist", "/NH", "/FO", "CSV"],
            capture_output=True, text=True, encoding="gbk", errors="ignore",
            timeout=10, creationflags=_no_window(),
        ).stdout or ""
        return "qq.exe" in out.lower()
    except Exception:
        return False


def find_qq(root: str | Path | None = None) -> str | None:
    conf = str(_read_config(root_of(root)).get("qq_path") or "").strip()
    if conf and Path(conf).exists():
        return conf
    for p in _QQ_CANDIDATES:
        if Path(p).exists():
            return p
    local = os.getenv("LOCALAPPDATA") or ""
    if local:
        p = Path(local) / "Programs" / "Tencent" / "QQNT" / "QQ.exe"
        if p.exists():
            return str(p)
    return None


def ensure_qq(root: str | Path | None = None) -> bool:
    """SnowLuma 靠注入已在跑的 QQ，所以得先把 QQ 拉起来。"""
    if qq_running():
        return True
    exe = find_qq(root)
    if not exe:
        return False
    subprocess.Popen([exe], close_fds=True)
    return True


def kill_qq() -> None:
    if sys.platform != "win32":
        return
    subprocess.run(["cmd", "/c", "taskkill /F /IM QQ.exe"],
                   capture_output=True, creationflags=_no_window())


def start(root: str | Path | None = None, account: str = "", quiet: bool = True) -> bool:
    """拉起协议端；已经活着就直接返回 True。"""
    root = root_of(root)
    name = backend(root)
    if is_up(root, name):
        return True
    if name == "napcat":
        return _start_napcat(root, account, quiet)
    return _start_snowluma(root)


def _start_napcat(root: Path, account: str, quiet: bool) -> bool:
    bat = root / "napcat" / "launcher-user-silent.bat"
    if not bat.exists():
        return False
    from .account import napcat_launch_args

    subprocess.Popen(["cmd", "/c", str(bat), *napcat_launch_args(account, quiet=quiet)],
                     cwd=str(root / "napcat"), creationflags=_no_window())
    return True


def snowluma_home(root: str | Path | None = None) -> Path:
    """SnowLuma 装在哪。

    注意：不能默认放在工作区里。DSH 工作区（E:\\dsqq）整棵树带 Low 完整性标签，
    那里的 node.exe 启动出来是 Low 进程，UIPI 会拦住它注入 Medium 的 QQ，
    面板会报「Node 完整性过低 / 0 进程可注入」。所以默认放 E:\\snowluma。
    """
    env = (os.getenv("SNOWLUMA_HOME") or "").strip()
    if env and (Path(env) / "index.mjs").exists():
        return Path(env)
    conf = str(_read_config(root_of(root)).get("snowluma_home") or "").strip()
    if conf and (Path(conf) / "index.mjs").exists():
        return Path(conf)
    for cand in (Path("E:/snowluma"), root_of(root) / "snowluma"):
        if (cand / "index.mjs").exists():
            return cand
    return root_of(root) / "snowluma"


def _start_snowluma(root: Path) -> bool:
    """用发行包里自带的 node.exe 跑 index.mjs（系统 node 版本可能不满足）。"""
    home = snowluma_home(root)
    entry = home / "index.mjs"
    if not entry.exists():
        return False
    node = home / "node.exe"
    exe = str(node) if node.exists() else "node"
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    logf = open(logs / "snowluma.log", "a", encoding="utf-8", buffering=1)
    subprocess.Popen([exe, str(entry)], cwd=str(home), stdout=logf, stderr=logf,
                     close_fds=True, creationflags=_no_window())
    # 注入目标必须是活着的 QQ：hookAutoLoad 只能发现已经在跑的进程
    ensure_qq(root)
    return True


def restart(root: str | Path | None = None, account: str = "") -> bool:
    """QQ 掉线后的重启用：干掉 QQ → 等协议端重新注入/重新引导。"""
    root = root_of(root)
    kill_qq()
    time.sleep(3)
    if backend(root) == "snowluma" and not is_up(root):
        return start(root, account)
    return True


def wait_up(root: str | Path | None = None, seconds: int = 60) -> bool:
    root = root_of(root)
    deadline = time.time() + seconds
    while time.time() < deadline:
        if is_up(root):
            return True
        time.sleep(1)
    return False


def login_hint(root: str | Path | None = None) -> str:
    """给使用者看的一句话：这个后端该怎么登录。"""
    if backend(root) == "snowluma":
        return ("SnowLuma 只支持扫码：QQ 窗口会自己弹出来，用手机 QQ 扫码登录；"
                f"管理面板 http://127.0.0.1:{webui_port('snowluma')}/ （临时密码见 logs/snowluma.log）")
    return f"NapCat 登录页：{webui_url(root, 'napcat')}"
