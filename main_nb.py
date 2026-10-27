"""NoneBot2 启动入口 —— 替代旧的 main.py（自研 OneBot 适配器）。

被 boot.py / watchdog.py / login_qr.py / open_console.vbs 拉起的就是这个文件。

角色分工：
    NoneBot2 + nonebot-adapter-onebot   ← 框架层（连接、事件、插件、日志、生命周期）
    qqbot.*（记忆 / 情绪 / 人格 / 语音 / 表情包 / 抖音 / 主动开聊） ← 业务层，原样复用
    qqbot.http_api（:8088）              ← 本机发送接口 + 网页配置台，保留

旧的 main.py 仍然在，随时可以退回去跑（git 里也没删）。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)  # 老代码到处用 data/ stickers/ logs/ 这类相对路径
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# pythonw 启动时没有控制台，sys.stdout/stderr 是 None，uvicorn / loguru 会直接炸
if sys.stdout is None or sys.stderr is None:
    (ROOT / "logs").mkdir(exist_ok=True)
    if sys.stdout is None:
        sys.stdout = open(ROOT / "logs" / "stdout.log", "a", encoding="utf-8", buffering=1)
    if sys.stderr is None:
        sys.stderr = open(ROOT / "logs" / "stderr.log", "a", encoding="utf-8", buffering=1)

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBot11Adapter
from nonebot.log import logger as nb_logger

from qqbot.config import load_config
from qqbot.utils_log import setup_logging

log = logging.getLogger("nb.main")


def _attach_nonebot_file_log() -> None:
    """NoneBot(loguru) 的输出同时写一份到 logs/nonebot.log。"""
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    nb_logger.add(
        str(logs / "nonebot.log"),
        level="INFO",  # 文件里只留 INFO 以上，免得 DEBUG 把日志撑爆
        rotation="10 MB",
        retention=5,
        encoding="utf-8",
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )


def _env_defaults(cfg) -> dict[str, str]:
    """按 config.yaml 算出框架层该有的配置项（端口跟老版一致：8199）。"""
    ob = cfg.section("onebot11") or {}
    rev = ob.get("reverse") or {}
    return {
        "DRIVER": "~fastapi",
        "HOST": str(rev.get("host") or "127.0.0.1"),
        "PORT": str(rev.get("port") or 8199),
        "LOG_LEVEL": cfg.log_level,
        "DEBUG": "false",
        "ONEBOT_ACCESS_TOKEN": str(ob.get("access_token") or ""),
        "COMMAND_START": '["/"]',
        "COMMAND_SEP": '["."]',
    }


def ensure_env_file(path: Path, cfg) -> None:
    """nb.env 不存在就生成；存在就补齐缺的键（老包装上新版也不会缺配置）。

    用户已经填过的值一律保留，只补缺、不覆盖。
    """
    wanted = _env_defaults(cfg)
    existing: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, _, v = s.partition("=")
            existing[k.strip()] = v.strip()

    merged = {k: existing.get(k, v) for k, v in wanted.items()}
    extras = {k: v for k, v in existing.items() if k not in wanted}
    already_ok = path.exists() and not extras and all(existing.get(k) == v for k, v in wanted.items())
    if already_ok:
        return

    lines = [
        "# NoneBot2 运行配置：main_nb.py 首次启动时自动生成，之后只补缺不覆盖",
        "# 端口跟老版一致（8199 给 NapCat 反向 WS）；改完要重启服务",
        "",
    ]
    lines += [f"{k}={v}" for k, v in merged.items()]
    if extras:
        lines += ["", "# 额外自定义项"] + [f"{k}={v}" for k, v in extras.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    cfg = load_config(ROOT / "config.yaml")
    setup_logging(cfg.log_level)          # logs/qq-bridge.log，跟以前一样的日志位置
    _attach_nonebot_file_log()

    # 读根目录 nb.env（没有就按 config.yaml 生成；文件名避开 .env，本机安全策略不让写）
    ensure_env_file(ROOT / "nb.env", cfg)
    nonebot.init(_env_file=str(ROOT / "nb.env"))
    driver = nonebot.get_driver()
    driver.register_adapter(OneBot11Adapter)

    nonebot.load_plugin("nb.plugins.nb_sys")          # 框架原生指令 /nb
    plugin = nonebot.load_plugin("nb.plugins.legacy_bridge")   # 老引擎接管聊天
    if plugin is None:
        raise RuntimeError("legacy_bridge 插件加载失败，检查上面的报错")

    from nb.plugins import legacy_bridge

    api_cfg: dict[str, Any] = dict(cfg.section("http_api"))
    if os.getenv("XN_HTTP_PORT"):  # 自测 / 双开验证时换个端口，不影响线上
        api_cfg["port"] = int(os.environ["XN_HTTP_PORT"])
    holder: dict[str, Any] = {}

    @driver.on_bot_connect
    async def _on_bot_connect(bot) -> None:
        """NapCat 连上来后把真实 QQ 号写进 config.yaml。

        装机时不用提前问机器人号：扫码登录 → 这里记下来 → 以后静默登录同一个号。
        """
        from qqbot.account import bot_account, remember_account

        self_id = str(getattr(bot, "self_id", "") or "")
        if not self_id.isdigit():
            return
        if bot_account(ROOT) == self_id:
            return
        if remember_account(ROOT, self_id):
            log.info("已把登录的机器人号写入 config.yaml：bot_qq=%s", self_id)

    @driver.on_startup
    async def _startup() -> None:
        # 老引擎的主动搭话 / 日记 / 备份循环要 create_task，必须活在事件循环里
        legacy_bridge.boot()
        if api_cfg.get("enabled", True):
            from qqbot.http_api import HttpApi

            api = HttpApi(legacy_bridge.SHIM, api_cfg)
            await api.start()
            holder["api"] = api
        nbc = nonebot.get_driver().config
        log.info(
            "服务已启动｜框架 nonebot2 %s｜反向 WS %s:%s｜本机接口 http://%s:%s",
            nonebot.__version__,
            nbc.host,
            nbc.port,
            api_cfg.get("host", "127.0.0.1"),
            api_cfg.get("port", 8088),
        )

    @driver.on_shutdown
    async def _shutdown() -> None:
        api = holder.pop("api", None)
        if api is not None:
            await api.stop()
        log.info("服务已关闭")

    try:
        nonebot.run()
    except OSError as exc:
        log.error("启动失败：端口可能被占用（%s）。先停掉旧实例再试。", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
