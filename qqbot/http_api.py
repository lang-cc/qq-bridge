"""本地 HTTP 发送接口：任何脚本 / 程序 POST 一下，就能让这个 QQ 号发消息。

启动后可用：
  POST http://127.0.0.1:8088/send      {"group_id": 123, "message": "你好"}
  POST http://127.0.0.1:8088/send/text {"user_id": 456, "text": "你好"}
  POST .../send/image {"group_id":123, "src":"E:/a.png"}   # 或 http 链接 / base64://
  POST .../send/voice {"group_id":123, "src":"E:/a.silk"}
  POST .../send/video | /send/file | /send/link | /send/screenshot
  GET  .../status
鉴权：配置了 token 就在请求头带 X-Token，或 URL 上加 ?token=
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any

from aiohttp import web

from . import message as msg
from . import version as app_version

log = logging.getLogger("qqbot.http_api")


def _j(data: Any, status: int = 200) -> web.Response:
    """返回 JSON，中文不转义。"""
    return web.Response(
        body=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        status=status,
        content_type="application/json",
    )


def _is_loopback(host: str) -> bool:
    """host 是不是只听本机（127.0.0.1 / localhost / ::1）。"""
    h = (host or "").strip().lower()
    return h in ("127.0.0.1", "localhost", "::1", "0:0:0:0:0:0:0:1") or h.startswith("127.")


class HttpApi:
    def __init__(self, bot: Any, cfg: dict | None = None) -> None:
        self.bot = bot
        self.cfg = cfg or {}
        self.host = str(self.cfg.get("host") or "127.0.0.1")
        self.port = int(self.cfg.get("port") or 8088)
        self.token = str(self.cfg.get("token") or "")
        self._runner: Any = None
        self.started_at: float = 0.0          # 服务起跑时间（主页「已运行」用）

    # ------------------------------------------------------------ 生命周期
    async def start(self) -> None:
        @web.middleware
        async def errors(request: web.Request, handler: Any) -> web.StreamResponse:
            try:
                return await handler(request)
            except web.HTTPException:
                raise
            except ConnectionError as exc:
                return _j({"ok": False, "error": f"协议端未连接：{exc}"}, status=503)
            except (TimeoutError, asyncio.TimeoutError) as exc:
                return _j({"ok": False, "error": f"超时：{exc}"}, status=504)
            except Exception as exc:
                log.exception("发送接口异常")
                return _j({"ok": False, "error": repr(exc)}, status=502)

        app = web.Application(middlewares=[errors])
        app.add_routes(
            [
                web.get("/", self.h_doc),
                web.get("/doc", self.h_doc),
                web.get("/status", self.h_status),
                web.post("/send", self.h_send),
                web.post("/send/text", self.h_text),
                web.post("/send/image", self.h_image),
                web.post("/send/voice", self.h_voice),
                web.post("/send/video", self.h_video),
                web.post("/send/file", self.h_file),
                web.post("/send/link", self.h_link),
                web.post("/send/screenshot", self.h_screenshot),
                # ---- 配置界面 ----
                web.get("/admin", self.h_admin),
                web.get("/admin/config", self.h_admin_config),
                web.post("/admin/save", self.h_admin_save),
                web.get("/admin/models", self.h_admin_models),
                web.post("/admin/test", self.h_admin_test),
                web.post("/admin/test_tts", self.h_admin_test_tts),
                web.post("/admin/reload", self.h_admin_reload),
                web.post("/admin/share", self.h_admin_share),
                web.post("/admin/diary", self.h_admin_diary),
                web.post("/admin/image", self.h_admin_image),
                web.get("/admin/usage", self.h_admin_usage),
                web.get("/admin/logs", self.h_admin_logs),
                web.get("/admin/memory", self.h_admin_memory),
                web.post("/admin/memory/clear", self.h_admin_memory_clear),
                web.get("/admin/memory/export", self.h_admin_memory_export),
                web.post("/admin/login", self.h_admin_login),
                web.get("/admin/qr", self.h_admin_qr),
                web.get("/admin/qr.png", self.h_admin_qr_png),
                web.post("/admin/qr/refresh", self.h_admin_qr_refresh),
                web.post("/admin/watchdog", self.h_admin_watchdog),
                web.post("/admin/restart", self.h_admin_restart),
                web.post("/admin/backup", self.h_admin_backup),
                web.get("/admin/plugins", self.h_admin_plugins),
                web.post("/admin/plugins/toggle", self.h_admin_plugin_toggle),
                web.get("/admin/features", self.h_admin_features),
                web.get("/admin/napcat", self.h_admin_napcat),
                web.get("/admin/protocol", self.h_admin_napcat),
                web.get("/admin/health", self.h_admin_health),
                web.post("/admin/whitelist", self.h_admin_whitelist),
                web.post("/admin/features/toggle", self.h_admin_feature_toggle),
            ]
        )
        self._runner = web.AppRunner(app)
        await self._runner.setup()

        # 交付保险：绑到非回环地址却没有 token，等于把「改配置 / 看聊天记录」的权限
        # 开放给整个网络。这种情况一律退回只听本机，并大声记一条日志。
        if not _is_loopback(self.host) and not self.token:
            log.error(
                "http_api.host=%s 但 token 为空 → 拒绝对外暴露，退回 127.0.0.1。"
                "要公网访问请先设 http_api.token 为随机串。", self.host,
            )
            self.host = "127.0.0.1"

        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        import time as _t
        if not self.started_at:
            self.started_at = _t.time()
        # 访问日志（页面每 8 秒轮询 /status）会淹没有用信息，降到 WARNING
        logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
        log.info("发送接口已启动: http://%s:%s（token：%s）", self.host, self.port, "已启用" if self.token else "未启用")

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    # ------------------------------------------------------------ 工具
    def _auth(self, request: web.Request) -> None:
        if not self.token:
            return
        if request.headers.get("X-Token") == self.token or request.query.get("token") == self.token:
            return
        raise web.HTTPUnauthorized(text='{"ok":false,"error":"invalid token"}', content_type="application/json")

    async def _body(self, request: web.Request) -> dict:
        try:
            data = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text='{"ok":false,"error":"body 必须是 JSON"}', content_type="application/json")
        if not isinstance(data, dict):
            raise web.HTTPBadRequest(text='{"ok":false,"error":"body 必须是 JSON 对象"}', content_type="application/json")
        return data

    async def _send_to(self, data: dict, payload: Any) -> dict:
        group_id = data.get("group_id")
        user_id = data.get("user_id")
        if group_id is not None:
            return await self.bot.adapter.send_group_msg(group_id, payload)
        if user_id is not None:
            return await self.bot.adapter.send_private_msg(user_id, payload)
        raise web.HTTPBadRequest(text='{"ok":false,"error":"需要 group_id 或 user_id"}', content_type="application/json")

    @staticmethod
    def _ok(result: Any) -> web.Response:
        return _j({"ok": True, "data": result})

    # ------------------------------------------------------------ 路由
    async def h_doc(self, request: web.Request) -> web.Response:
        """手机端交付说明页（带 token 才给看，里面含密钥）。"""
        self._auth(request)
        from pathlib import Path

        p = Path("static/doc.html")
        if not p.exists():
            return web.Response(text="说明页还没上传", status=404, content_type="text/plain", charset="utf-8")
        return web.Response(body=p.read_bytes(), content_type="text/html", charset="utf-8")

    async def h_status(self, request: web.Request) -> web.Response:
        # /status 不鉴权：看门狗、自检、部署脚本都要用它探活（只返回在线信息，不含敏感内容）
        data: dict[str, Any] = {
            "ok": True,
            "adapter": self.bot.adapter.name,
            "self_id": self.bot.self_id,
            "connected": getattr(self.bot.adapter, "_ws", None) is not None,
            "plugins": len(self.bot.router.handlers),
        }
        try:  # 版本号一起吐出来：更新完对一下就知道新代码生效没
            data["version"] = app_version.info()
        except Exception:  # 版本读不出来不能影响探活
            pass
        return _j(data)

    async def h_send(self, request: web.Request) -> web.Response:
        """通用接口：message 可以是字符串，也可以是消息段数组。"""
        self._auth(request)
        data = await self._body(request)
        payload = data.get("message")
        if payload is None:
            raise web.HTTPBadRequest(text='{"ok":false,"error":"缺少 message"}', content_type="application/json")
        return self._ok(await self._send_to(data, msg.build(payload)))

    async def h_text(self, request: web.Request) -> web.Response:
        self._auth(request)
        data = await self._body(request)
        payload = [msg.text(data.get("text", ""))]
        if data.get("at"):
            payload.insert(0, msg.text(" "))
            payload.insert(0, msg.at(data["at"]))
        return self._ok(await self._send_to(data, payload))

    async def h_image(self, request: web.Request) -> web.Response:
        self._auth(request)
        data = await self._body(request)
        if data.get("base64"):
            payload = [msg.image_bytes(bytes(data["base64"], "utf-8") if isinstance(data["base64"], str) else data["base64"])]
        else:
            payload = [msg.image(data.get("src", ""))]
        return self._ok(await self._send_to(data, payload))

    async def h_voice(self, request: web.Request) -> web.Response:
        self._auth(request)
        data = await self._body(request)
        from .voice import prepare

        src = prepare(data.get("src", ""))
        return self._ok(await self._send_to(data, [msg.record(src)]))

    async def h_video(self, request: web.Request) -> web.Response:
        self._auth(request)
        data = await self._body(request)
        return self._ok(await self._send_to(data, [msg.video(data.get("src", ""))]))

    async def h_file(self, request: web.Request) -> web.Response:
        self._auth(request)
        data = await self._body(request)
        return self._ok(await self._send_to(data, [msg.file(data.get("src", ""), data.get("name"))]))

    async def h_link(self, request: web.Request) -> web.Response:
        self._auth(request)
        data = await self._body(request)
        url = data.get("url", "")
        if data.get("card", True):
            payload = [msg.link(url, data.get("title", ""), data.get("desc", ""), data.get("preview", ""))]
        else:
            payload = [msg.link_plain(url, data.get("title", ""))]
        return self._ok(await self._send_to(data, payload))

    async def h_screenshot(self, request: web.Request) -> web.Response:
        self._auth(request)
        data = await self._body(request)
        from .screenshot import capture_desktop, capture_url

        url = data.get("url")
        if url:
            path = capture_url(url, width=int(data.get("width") or 1280), height=int(data.get("height") or 800))
        else:
            bbox = data.get("bbox")
            path = capture_desktop(bbox=tuple(bbox) if bbox else None)
        return self._ok(await self._send_to(data, [msg.image(path)]))

    # ------------------------------------------------------------ 配置界面
    def _raw(self) -> dict:
        cfg = getattr(self.bot, "config", None)
        return dict(getattr(cfg, "raw", {}) or {})

    async def h_admin(self, request: web.Request) -> web.Response:
        self._auth(request)
        from .admin import PAGE

        return web.Response(text=PAGE, content_type="text/html", charset="utf-8")

    async def h_admin_config(self, request: web.Request) -> web.Response:
        self._auth(request)
        raw = self._raw()
        # allow / robot 一起带上，页面才能显示白名单和机器人号（只读展示）
        return _j({
            "autoreply": raw.get("autoreply") or {},
            "allow": raw.get("allow") or {},
            "robot": raw.get("robot") or {},
            "bot_qq": raw.get("bot_qq") or "",
            "city": raw.get("city") or "",
        })

    async def h_admin_save(self, request: web.Request) -> web.Response:
        self._auth(request)
        from pathlib import Path

        import yaml

        from .admin import save_config

        data = await self._body(request)
        autoreply = data.get("autoreply") or {}
        path = Path("config.yaml")
        raw: dict = {}
        if path.exists():
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw["autoreply"] = autoreply
        save_config(raw, path)
        cfg = getattr(self.bot, "config", None)
        if cfg is not None:
            cfg.raw["autoreply"] = autoreply
        log.info("配置已通过网页更新（已备份 config.yaml.bak）")
        return _j({"ok": True})

    async def h_admin_models(self, request: web.Request) -> web.Response:
        self._auth(request)
        from .admin import list_models

        return _j(await list_models(self._raw().get("autoreply") or {}))

    async def h_admin_test(self, request: web.Request) -> web.Response:
        self._auth(request)
        from .admin import test_llm

        data = await self._body(request)
        autoreply = data.get("autoreply") or self._raw().get("autoreply") or {}
        return _j(await test_llm(autoreply, data.get("text") or "在吗"))

    async def h_admin_reload(self, request: web.Request) -> web.Response:
        self._auth(request)
        cfg = getattr(self.bot, "config", None)
        if cfg is None:
            return _j({"ok": False, "error": "no config"})
        try:
            cfg.reload("config.yaml")
            log.info("配置已从磁盘重载")
            return _j({"ok": True})
        except Exception as exc:
            return _j({"ok": False, "error": repr(exc)})

    async def h_admin_share(self, request: web.Request) -> web.Response:
        """手动触发一次分享：{"chat":"u123","kind":"douyin"}"""
        self._auth(request)
        data = await self._body(request)
        chat = str(data.get("chat") or "")
        kind = str(data.get("kind") or "douyin")
        if len(chat) < 2 or chat[0] not in ("u", "g"):
            return _j({"ok": False, "error": "chat 形如 u123 或 g456"})
        from .plugins import companion as comp

        engine = getattr(comp, "ENGINE", None)
        if engine is None:
            return _j({"ok": False, "error": "引擎未就绪"})
        ev = comp._Shell(
            group_id=int(chat[1:]) if chat.startswith("g") else None,
            user_id=int(chat[1:]) if chat.startswith("u") else None,
        )
        try:
            ok = await (engine._share_douyin(ev, chat) if kind == "douyin" else engine._share_video(ev, chat))
        except Exception as exc:
            log.warning("手动分享失败：%r", exc)
            return _j({"ok": False, "error": repr(exc)})
        return _j({"ok": bool(ok), "chat": chat, "kind": kind})

    async def h_admin_diary(self, request: web.Request) -> web.Response:
        """立刻写一篇日记：{"chat":"u123"}"""
        self._auth(request)
        data = await self._body(request)
        chat = str(data.get("chat") or "")
        if len(chat) < 2 or chat[0] not in ("u", "g"):
            return _j({"ok": False, "error": "chat 形如 u123"})
        from .plugins import companion as comp

        engine = getattr(comp, "ENGINE", None)
        if engine is None:
            return _j({"ok": False, "error": "引擎未就绪"})
        try:
            text = await engine._write_diary(chat, force=True)
        except Exception as exc:
            return _j({"ok": False, "error": repr(exc)})
        return _j({"ok": bool(text), "diary": text})

    async def h_admin_image(self, request: web.Request) -> web.Response:
        """让她做张图发过去：{"chat":"u123","text":"...","kind":"meme|quote"}"""
        self._auth(request)
        data = await self._body(request)
        chat = str(data.get("chat") or "")
        text = str(data.get("text") or "")
        kind = str(data.get("kind") or "auto")
        if len(chat) < 2 or chat[0] not in ("u", "g"):
            return _j({"ok": False, "error": "chat 形如 u123"})
        from .plugins import companion as comp

        engine = getattr(comp, "ENGINE", None)
        if engine is None:
            return _j({"ok": False, "error": "引擎未就绪"})
        ev = comp._Shell(
            group_id=int(chat[1:]) if chat.startswith("g") else None,
            user_id=int(chat[1:]) if chat.startswith("u") else None,
        )
        try:
            ok = await engine._send_made_image(ev, chat, text, kind=kind)
        except Exception as exc:
            return _j({"ok": False, "error": repr(exc)})
        return _j({"ok": bool(ok)})

    # ---------------- 插件开关 ----------------
    def _legacy_router(self):
        from nb.plugins.legacy_bridge import SHIM

        return SHIM

    async def h_admin_plugins(self, request: web.Request) -> web.Response:
        self._auth(request)
        from .plugin_info import build
        from . import toggles

        shim = self._legacy_router()
        return _j({
            "ok": True,
            "plugins": build(shim.router),
            "disabled": sorted(toggles.disabled()),
        })

    async def h_admin_plugin_toggle(self, request: web.Request) -> web.Response:
        self._auth(request)
        from . import toggles
        from .admin import save_config

        data = await self._body(request)
        pid = str(data.get("id") or "").strip()
        if not pid:
            return _j({"ok": False, "error": "缺少插件 id"})
        enabled = bool(data.get("enabled"))
        new = toggles.toggle(pid, enabled)
        raw = self._raw()
        raw.setdefault("plugins", {})["disabled"] = sorted(new)
        save_config(raw)
        try:  # 让内存里的配置也跟上，免得再打开页面读到旧的
            self._legacy_router().config.raw = raw
        except Exception:
            pass
        log.info("插件开关：%s -> %s", pid, "开" if enabled else "关")
        return _j({"ok": True, "id": pid, "enabled": enabled, "disabled": sorted(new)})

    # ---------------- 协议端（SnowLuma / NapCat） ----------------
    def _protocol(self) -> dict:
        """协议端面板信息：以 qqbot.proto 为准（config.yaml 的 protocol_backend）。

        以前这里写死 napcat/config/webui.json 和 6099 —— 换成 SnowLuma 后都没了。
        现在端口、地址、二维码来源统一由 qqbot/proto.py 回答，各处不用再各写一份。
        """
        from urllib.parse import urlparse

        kind, url, token = "snowluma", "http://127.0.0.1:5099", ""
        label = "SnowLuma"
        try:
            from . import proto as _proto

            kind = _proto.backend()
            url = _proto.webui_url()
            label = {"snowluma": "SnowLuma", "napcat": "NapCat"}.get(kind, kind or "协议端")
            if kind == "napcat":
                token = _proto.napcat_webui_token() or ""
        except Exception as exc:  # proto 模块不在就退回老办法，别把面板搞挂
            log.debug("proto 模块不可用，退回 protocol 段：%r", exc)
            try:
                from .config import load_config

                sec = load_config("config.yaml").section("protocol") or {}
                kind = str(sec.get("kind") or kind)
                url = str(sec.get("webui") or url)
                token = str(sec.get("webui_token") or "")
                label = {"snowluma": "SnowLuma", "napcat": "NapCat"}.get(kind, kind or "协议端")
            except Exception as exc2:
                log.debug("读 protocol 配置也失败：%r", exc2)

        u = urlparse(url if "//" in url else "http://" + url)
        port = u.port or (443 if u.scheme == "https" else 80)
        webui = url.rstrip("/")
        if token and "token=" not in webui:
            webui = "%s/?token=%s" % (webui, token)

        # 控制台是唯一入口：QQ 在不在、面板账号密码、登录该怎么做，一并在这一处答完，
        # 让人不用再去 5099 翻日志找那个每次重启都会变的一次性密码。
        qq_running, we_user, we_pass, hint = False, "", "", ""
        try:
            from . import proto as _proto

            qq_running = _proto.qq_running()
            we_user, we_pass = self._snowluma_webui_cred(kind)
            hint = _proto.login_hint() if kind != "napcat" else ""
        except Exception as exc:
            log.debug("补协议端细节失败：%r", exc)

        return {
            "kind": kind,
            "label": label,
            "url": url.rstrip("/"),
            "host": u.hostname or "127.0.0.1",
            "port": port,
            "token": token,
            "webui": webui,
            # 只有 NapCat 会把二维码落到本地文件；SnowLuma 只能在它自己的窗口/面板里扫
            "has_qr": kind == "napcat",
            "qq_running": qq_running,
            "webui_user": we_user,
            "webui_pass": we_pass,
            "login_hint": hint,
        }

    @staticmethod
    def _snowluma_webui_cred(kind: str) -> tuple[str, str]:
        """从 SnowLuma 的 stdout 日志里捞最近一次打印的 WebUI 初始账号密码。

        SnowLuma 的 WebUI 密码只在启动时打印一次，且每次重启都会重新生成 ——
        放在控制台里直接展示，省得用户去翻 logs/stdout.log。
        """
        if kind != "snowluma":
            return "", ""
        import re
        from pathlib import Path

        try:
            from . import proto as _proto

            home = Path(_proto.snowluma_home())
        except Exception:
            home = Path("E:/snowluma")
        logf = home / "logs" / "stdout.log"
        try:
            raw = logf.read_bytes()
        except OSError:
            return "", ""
        tail = raw[-200_000:].decode("utf-8", "replace")
        hits = re.findall(r"initial credentials:\s*user=(\S+)\s+password=(\S+)", tail)
        return hits[-1] if hits else ("", "")

    async def h_admin_napcat(self, request: web.Request) -> web.Response:
        """协议端面板地址 + 密码（配置台主页上要给用户看）。路由名保留 napcat 是为了兼容老调用。"""
        self._auth(request)
        info = self._protocol()
        info["ok"] = True
        return _j(info)

    # ---------------- 白名单（网页上直接加/删） ----------------
    async def h_admin_whitelist(self, request: web.Request) -> web.Response:
        """把白名单整份写回 config.yaml 并立即生效（不用重启）。"""
        self._auth(request)
        from .admin import edit_whitelist

        data = await self._body(request)
        kind = str(data.get("kind") or "users")
        if kind not in ("users", "groups"):
            return _j({"ok": False, "error": "kind 只能是 users / groups"}, status=400)
        values = data.get("values")
        if not isinstance(values, list):
            return _j({"ok": False, "error": "values 必须是数组"}, status=400)

        clean: list[str] = []
        for v in values:
            s = str(v).strip().strip("'\"")
            if not s:
                continue
            if not s.isdigit() or not (4 <= len(s) <= 13):
                return _j({"ok": False, "error": f"「{s[:20]}」不是合法号码（纯数字 4–13 位）"}, status=400)
            if s not in clean:
                clean.append(s)
        if len(clean) > 200:
            return _j({"ok": False, "error": "最多 200 个"}, status=400)

        try:
            saved = edit_whitelist(kind, clean)
        except Exception as exc:
            log.warning("白名单写入失败：%r", exc)
            return _j({"ok": False, "error": f"写 config.yaml 失败：{exc!r}"}, status=500)

        # 内存里的配置同步换掉，下一句消息就按新名单判断
        cfgobj = getattr(self.bot, "config", None)
        try:
            ar = dict((cfgobj.raw or {}).get("autoreply") or {})
            wl = dict(ar.get("whitelist") or {})
            wl[kind] = saved
            ar["whitelist"] = wl
            cfgobj.raw["autoreply"] = ar
        except Exception as exc:
            log.warning("白名单写回内存失败：%r", exc)
        engine = self._engine()
        if engine is not None:
            try:
                engine.refresh()
            except Exception:
                pass

        now = {}
        if engine is not None:
            now = dict(engine.cfg.get("whitelist") or {})
        if not now:
            now = dict((((cfgobj.raw or {}).get("autoreply") or {}).get("whitelist") or {})) if cfgobj else {}
        return _j({
            "ok": True,
            "kind": kind,
            "values": saved,
            "whitelist": {
                "users": [str(x) for x in (now.get("users") or [])],
                "groups": [str(x) for x in (now.get("groups") or [])],
                "enabled": bool(now.get("enabled", True)),
            },
        })

    # ---------------- 主页「服务在线」监控 ----------------
    async def h_admin_health(self, request: web.Request) -> web.Response:
        """逐个探一遍：谁在线、谁不在。

        每项都带超时（本地 0.35 秒、外网 1.2 秒），全部不通也只卡一两秒，
        不会把配置台首页拖死。
        """
        self._auth(request)
        import socket
        import time
        from urllib.parse import urlparse

        def tcp(port: int, host: str = "127.0.0.1", timeout: float = 0.35) -> bool:
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    return True
            except Exception:
                return False

        def ago(sec: float) -> str:
            sec = int(max(0, sec))
            d, sec = divmod(sec, 86400)
            h, sec = divmod(sec, 3600)
            m, s = divmod(sec, 60)
            if d:
                return f"{d} 天 {h} 小时"
            if h:
                return f"{h} 小时 {m} 分"
            if m:
                return f"{m} 分 {s} 秒"
            return f"{s} 秒"

        items: list[dict] = []

        def add(key: str, name: str, ok: bool, detail: str = "", tip: str = "") -> None:
            items.append({"key": key, "name": name, "ok": bool(ok), "detail": detail, "tip": tip})

        engine = self._engine()
        cfg = dict(getattr(engine, "cfg", None) or {})

        # 1 机器人服务：能把这个请求答上来，就说明它活着
        up = time.time() - self.started_at if self.started_at else 0
        add("service", "机器人服务", True, f"本机 :{self.port} · 已运行 {ago(up)}",
            "重启：本页「重启服务」")

        # 2 框架层
        try:
            import nonebot

            n_ad = len(getattr(nonebot.get_driver(), "_adapters", {}) or {})
            add("framework", "NoneBot 框架", n_ad > 0,
                f"nonebot2 {nonebot.__version__} · 处理器 {len(self.bot.router.handlers)} 个",
                "看 logs/nonebot.log")
        except Exception as exc:
            add("framework", "NoneBot 框架", False, repr(exc)[:60], "看 logs/nonebot.log")

        # 3 QQ 登录（反向 WS 有没有连上）
        try:
            ws = getattr(self.bot.adapter, "_ws", None)
        except Exception:
            ws = None
        sid = getattr(self.bot, "self_id", 0) or 0
        add("qq", "QQ 登录", bool(ws) and bool(sid),
            f"账号 {sid}" if sid else "还没登录",
            "掉线了在主页点「扫码登录」")

        # 4 协议端（SnowLuma / NapCat）：探它的面板端口
        proto = self._protocol()
        nc_ok = tcp(int(proto["port"]), str(proto["host"]))
        add("protocol", f"协议端 · {proto['label']}", nc_ok,
            f"WebUI {proto['host']}:{proto['port']} 在线" if nc_ok
            else f"{proto['host']}:{proto['port']} 连不上",
            "把协议端拉起来，再在面板里确认 QQ 已登录")

        # 5 模型接口（只探 TCP 握手，不发请求、不花钱）
        llm = cfg.get("llm") or {}
        base = str(llm.get("base_url") or "")
        host, port, lat = "—", 0, 0.0
        llm_ok = False
        if base:
            u = urlparse(base if "//" in base else "https://" + base)
            host = u.hostname or "—"
            port = u.port or (443 if u.scheme == "https" else 80)
            t0 = time.perf_counter()
            llm_ok = tcp(port, host, timeout=1.2)
            lat = (time.perf_counter() - t0) * 1000
        add("llm", "模型接口", llm_ok,
            f"{host}:{port} · {lat:.0f}ms · {llm.get('model') or '未配置'}" if llm_ok
            else f"{host if base else '未配置'} 连不上",
            "去「模型」页改 base_url / 密钥")

        # 6 掉线自愈（看门狗占着 9335 当单实例锁）
        wd_ok = tcp(9335)
        add("watchdog", "掉线自愈", wd_ok, "看门狗在跑" if wd_ok else "看门狗没起",
            "本页「开掉线自愈」")

        # 7 语音合成（只看配置是否就绪，不试合成）
        tts = cfg.get("tts") or {}
        tts_ok = bool(tts.get("enabled")) and bool(tts.get("provider") or tts.get("api_key"))
        add("tts", "语音合成", tts_ok,
            f"{tts.get('provider') or '未配置'} · {str(tts.get('voice') or '')[:40]}" if tts_ok
            else "没配语音",
            "config.yaml → autoreply.tts")

        # 8 记忆库（能查就说明库没坏）
        try:
            store = engine.store
            ps = store.personas()
            n_msg = 0
            for p in ps:
                try:
                    row = store.memory(p["id"])._conn.execute("SELECT COUNT(*) FROM msg").fetchone()
                    n_msg += int(row[0] or 0) if row else 0
                except Exception:
                    pass
            add("memory", "记忆库", bool(ps), f"{len(ps)} 个人格 · {n_msg} 条对话", "看「记忆」页")
        except Exception as exc:
            add("memory", "记忆库", False, repr(exc)[:60], "看「记忆」页")

        online = sum(1 for x in items if x["ok"])
        return _j({"ok": True, "items": items, "online": online,
                   "total": len(items), "at": int(time.time())})

    # ---------------- 功能开关（心情 / 好感度 / 表情包 / 语音 …） ----------------
    def _engine(self):
        from .plugins import companion as comp

        return getattr(comp, "ENGINE", None)

    async def h_admin_features(self, request: web.Request) -> web.Response:
        self._auth(request)
        from .features import build

        engine = self._engine()
        cfg = dict(getattr(engine, "cfg", None) or self._raw().get("autoreply") or {})
        return _j({"ok": True, "features": build(cfg)})

    async def h_admin_feature_toggle(self, request: web.Request) -> web.Response:
        self._auth(request)
        from .admin import save_config
        from .features import apply as apply_feature

        data = await self._body(request)
        fid = str(data.get("id") or "").strip()
        if not fid:
            return _j({"ok": False, "error": "缺少功能 id"})
        enabled = bool(data.get("enabled"))

        raw = self._raw()
        block = raw.setdefault("autoreply", {})
        try:
            apply_feature(block, fid, enabled)
        except KeyError:
            return _j({"ok": False, "error": "未知功能：%s" % fid})
        save_config(raw)
        engine = self._engine()
        if engine is not None:
            try:  # 立即生效：直接改活着的引擎配置
                apply_feature(engine.cfg, fid, enabled)
            except Exception as exc:
                log.warning("功能开关写进运行引擎失败：%r", exc)
        log.info("功能开关：%s -> %s", fid, "开" if enabled else "关")
        return _j({"ok": True, "id": fid, "enabled": enabled})

    async def h_admin_usage(self, request: web.Request) -> web.Response:
        """用量统计：/admin/usage?days=7"""
        self._auth(request)
        days = int(request.query.get("days") or 1)
        from .plugins import companion as comp

        engine = getattr(comp, "ENGINE", None)
        if engine is None:
            return _j({"ok": False, "error": "引擎未就绪"})
        try:
            return _j({"ok": True, **engine.usage.summary(days=days)})
        except Exception as exc:
            return _j({"ok": False, "error": repr(exc)})

    # ---------------------------------------------------------------- 日志 / 记忆
    # 原来这两块在独立控制台 console.py（8089）里；现在合并进网页配置台，只留一个后台。
    async def h_admin_logs(self, request: web.Request) -> web.Response:
        """看日志尾巴：/admin/logs?file=qq-bridge|nonebot|watchdog&n=200"""
        self._auth(request)
        from pathlib import Path

        name = (request.query.get("file") or "qq-bridge").strip()
        if "/" in name or "\\" in name or ".." in name:
            return _j({"ok": False, "error": "file 只能是 qq-bridge / nonebot / watchdog"})
        try:
            n = max(1, min(2000, int(request.query.get("n") or 200)))
        except ValueError:
            n = 200

        path = Path("logs") / f"{name}.log"
        if not path.exists():
            return _j({"ok": False, "error": f"还没有 {path}"})
        try:
            with path.open("rb") as fh:
                fh.seek(0, 2)
                size = fh.tell()
                fh.seek(max(0, size - 512 * 1024))  # 只读最后 512KB
                tail = fh.read().decode("utf-8", "ignore")
            lines = tail.splitlines()[-n:]
            if request.query.get("clean", "1") not in ("0", "false"):
                # 默认隐藏访问日志噪声（自己的 /status 轮询会刷屏）
                noise = ("aiohttp.access", "uvicorn.access", "GET /status", "POST /admin")
                lines = [ln for ln in lines if not any(k in ln for k in noise)]
            return _j({"ok": True, "file": str(path), "lines": "\n".join(lines)})
        except Exception as exc:
            return _j({"ok": False, "error": repr(exc)})

    @staticmethod
    def _memory_files() -> list[tuple[str, Any]]:
        """找出所有记忆库：(人格 id, 路径)。新版每人格一个库，老版是 data/memory.db。"""
        from pathlib import Path

        out: list[tuple[str, Path]] = []
        base = Path("data")
        legacy = base / "memory.db"
        if legacy.exists():
            out.append(("", legacy))
        pdir = base / "personas"
        if pdir.is_dir():
            for sub in sorted(pdir.iterdir()):
                db = sub / "memory.db"
                if db.is_file():
                    out.append((sub.name, db))
        return out

    async def h_admin_memory(self, request: web.Request) -> web.Response:
        """记忆：不带 chat 列会话；带 chat 返回最近对话 + 记住的事实。"""
        self._auth(request)
        from .memory import Memory

        chat = (request.query.get("chat") or "").strip()
        persona = (request.query.get("persona") or "").strip()
        files = self._memory_files()
        if not files:
            return _j({"ok": True, "chats": []})

        try:
            if not chat:
                # 一个 QQ 只占一行：各人格的条数挂在 personas 里，页面上折叠起来
                groups: dict[str, dict] = {}
                for pid, path in files:
                    mem = Memory(str(path))
                    for cid in mem.known_chats(limit=50):
                        c = mem.message_count(cid)
                        g = groups.setdefault(cid, {"chat": cid, "count": 0, "personas": []})
                        g["count"] += c
                        g["personas"].append({"persona": pid, "count": c})
                chats = sorted(groups.values(), key=lambda x: x["count"], reverse=True)
                for g in chats:
                    g["personas"].sort(key=lambda x: x["count"], reverse=True)
                return _j({"ok": True, "chats": chats})

            target = files[0][1]
            for pid, path in files:
                if pid == persona:
                    target = path
                    break
            else:
                for _pid, path in files:  # 没指定人格就找哪个库里有这个会话
                    mem = Memory(str(path))
                    if mem.message_count(chat) > 0:
                        target = path
                        break
            mem = Memory(str(target))
            recent = mem.recent(chat, limit=40)
            return _j({
                "ok": True,
                "persona": persona,
                "chat": chat,
                "count": mem.message_count(chat),
                "summary": mem.get_summary(chat) or "",
                "facts": mem.facts(chat) or {},
                "recent": [{"role": m.get("role"), "content": m.get("content")} for m in recent],
            })
        except Exception as exc:
            return _j({"ok": False, "error": repr(exc)})

    async def h_admin_memory_export(self, request: web.Request) -> web.Response:
        """把记忆和人格一起打包下载（zip：人格设定 + 每个会话的记忆库 + 成长档案）。"""
        self._auth(request)
        import datetime as _dt
        import io as _io
        import zipfile
        from pathlib import Path as _Path

        base = _Path("data")
        buf = _io.BytesIO()
        try:
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for p in (base / "personas.yaml", base / "memory_router.db"):
                    if p.exists():
                        z.write(p, str(p.relative_to(base.parent)))
                for sub in ("personas", "growth"):
                    d = base / sub
                    if not d.exists():
                        continue
                    for f in d.rglob("*"):
                        if f.is_file():
                            z.write(f, str(f.relative_to(base.parent)))
        except Exception as exc:
            return _j({"ok": False, "error": repr(exc)})
        name = "memory-%s.zip" % _dt.datetime.now().strftime("%Y%m%d-%H%M")
        return web.Response(
            body=buf.getvalue(),
            content_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="%s"' % name},
        )

    async def h_admin_memory_clear(self, request: web.Request) -> web.Response:
        """清空某段记忆：{"persona": "xiaoyou", "chat": "u123"}"""
        self._auth(request)
        from .memory import Memory

        data = await self._body(request)
        chat = str(data.get("chat") or "").strip()
        persona = str(data.get("persona") or "").strip()
        if not chat:
            return _j({"ok": False, "error": "chat 必填"})
        files = self._memory_files()
        done: list[str] = []
        for pid, path in files:
            if persona and pid != persona:
                continue
            try:
                mem = Memory(str(path))
                if mem.message_count(chat) > 0:
                    mem.forget(chat)
                    done.append(pid)
                    if persona:
                        break
            except Exception as exc:
                return _j({"ok": False, "error": repr(exc)})
        if not done:
            return _j({"ok": False, "error": f"没找到 {chat} 的记忆"})
        return _j({"ok": True, "chat": chat, "personas": done})

    # ---------------------------------------------------------------- 动作按钮
    # 桌面面板删掉之后，扫码登录 / 掉线自愈 / 重启 / 备份 都收到网页配置台上。
    @staticmethod
    def _python_exe(windowless: bool = True):
        """优先用 .venv 里的 python（Windows 用 pythonw 免窗口，Linux 用 bin/python）。"""
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        win = root / ".venv" / "Scripts" / ("pythonw.exe" if windowless else "python.exe")
        if win.exists():
            return str(win)
        posix = root / ".venv" / "bin" / "python"
        if posix.exists():
            return str(posix)
        return sys.executable

    @staticmethod
    def _port_open(port: int) -> bool:
        import socket

        with socket.socket() as s:
            s.settimeout(0.35)
            return s.connect_ex(("127.0.0.1", port)) == 0

    def _spawn(self, script: str) -> bool:
        """后台拉起一个脚本（不阻塞、不影响本服务）。"""
        import subprocess
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        target = root / script
        if not target.exists():
            return False
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen([self._python_exe(), str(target)], cwd=str(root),
                         close_fds=True, creationflags=flags)
        return True

    # 扫码登录页：Linux 下没有桌面窗口，改成一个手机能直接看的网页，
    # 二维码从 NapCat 容器里取，自动刷新 + 显示登录状态。
    LOGIN_HTML = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>扫码登录</title>
<style>
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#0f1115;color:#e8eaf0;
display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;margin:0;gap:16px;padding:20px;box-sizing:border-box}
h3{margin:0;font-weight:600;font-size:17px}
img{width:min(76vw,300px);height:auto;background:#fff;border-radius:16px;padding:10px;display:block}
button{background:#2b6cff;border:0;color:#fff;padding:12px 22px;border-radius:11px;font-size:15px}
button[disabled]{opacity:.6}
#s{font-size:14px;color:#9aa4b2;min-height:20px}
#s.ok{color:#3ddc84}
</style></head><body>
<h3>用手机 QQ 扫码登录</h3>
<img id="q" src="/admin/qr.png?token=__TOKEN__&t=0" alt="二维码">
<button id="b" onclick="refresh()">换一张</button>
<div id="s">等待扫码…</div>
<script>
const T='__TOKEN__';
function tick(){document.getElementById('q').src='/admin/qr.png?token='+T+'&t='+Date.now();}
async function refresh(){const b=document.getElementById('b');b.disabled=true;b.textContent='刷新中…';
  try{await fetch('/admin/qr/refresh?token='+T,{method:'POST'});}catch(e){}
  setTimeout(()=>{tick();b.disabled=false;b.textContent='换一张';},16000);}
setInterval(async()=>{
  if(document.getElementById('s').classList.contains('ok'))return;
  tick();
  try{const d=await(await fetch('/status')).json();const s=document.getElementById('s');
    if(d.connected){s.textContent='已登录 ✅ QQ '+d.self_id;s.className='ok';}
  }catch(e){}
},5000);
</script></body></html>"""

    async def h_admin_login(self, request: web.Request) -> web.Response:
        """扫码登录：SnowLuma 走它自己的窗口/面板；NapCat 在 Windows 上拉起桌面窗口。"""
        self._auth(request)
        proto = self._protocol()
        if proto["kind"] != "napcat":
            hint = f"在 {proto['label']} 面板里扫码登录"
            try:
                from . import proto as _proto

                hint = _proto.login_hint() or hint
            except Exception:
                pass
            return _j({"ok": True, "url": proto["webui"], "hint": hint})
        if os.name != "nt":
            return _j({"ok": True, "url": f"/admin/qr?token={self.token}",
                       "hint": "已打开二维码页面，用手机 QQ 扫一下"})
        ok = self._spawn("login_qr.py")
        return _j({"ok": ok, "hint": "扫码窗口已弹出，用手机 QQ 扫一下" if ok else "没找到 login_qr.py"})

    async def h_admin_qr(self, request: web.Request) -> web.Response:
        """手机可直接打开的扫码登录页（只有 NapCat 会把码落成本地图片）。"""
        self._auth(request)
        proto = self._protocol()
        if proto["kind"] != "napcat" or not proto["has_qr"]:
            # SnowLuma 的二维码在 QQ 自己的窗口里，网页给不出码 —— 别让用户对着空白页等。
            hint = proto.get("login_hint") or "打开 QQ 窗口扫码登录"
            html = (
                "<!doctype html><html lang='zh'><meta charset='utf-8'>"
                "<body style=\"font-family:-apple-system,'Microsoft YaHei',sans-serif;"
                "max-width:640px;margin:12vh auto;padding:0 24px;line-height:1.7;color:#12211d\">"
                f"<h2 style='margin:0 0 12px'>{proto['label']} 没有网页二维码</h2>"
                f"<p style='color:#5d716c'>{hint}</p>"
                f"<p>协议端面板：<a href='{proto['webui']}' target='_blank' rel='noreferrer'>{proto['webui']}</a></p>"
                "<p style='color:#8b9d98;font-size:13px'>想回控制台：<a href='/admin'>/admin</a></p>"
                "</body></html>"
            )
            return web.Response(text=html, content_type="text/html", charset="utf-8")
        return web.Response(text=self.LOGIN_HTML.replace("__TOKEN__", self.token),
                            content_type="text/html")

    async def h_admin_test_tts(self, request: web.Request) -> web.Response:
        self._auth(request)
        from .admin import test_tts

        data = await self._body(request)
        autoreply = data.get("autoreply") or self._raw().get("autoreply") or {}
        return _j(await test_tts(autoreply))

    async def h_admin_qr_png(self, request: web.Request) -> web.Response:
        """登录二维码（只有 NapCat 会把码落到本地文件；SnowLuma 走面板/桌面扫码）。"""
        self._auth(request)
        from pathlib import Path

        if not self._protocol()["has_qr"]:
            return web.Response(status=404, text="no qr")
        raw = b""
        for rel in ("napcat/cache/qrcode.png", "napcat/cache/qrcode_big.png", "napcat/qrcode.png"):
            f = Path(rel)
            try:
                if f.exists() and f.stat().st_size > 200:
                    raw = f.read_bytes()
                    break
            except Exception:
                continue
        if not raw:
            import subprocess

            out = Path("/tmp/qqbot-qrcode.png")
            try:
                subprocess.run(["docker", "cp", "napcat:/app/napcat/cache/qrcode.png", str(out)],
                               capture_output=True, timeout=20)
                raw = out.read_bytes()
            except Exception as exc:
                log.debug("取二维码失败：%r", exc)
                raw = b""
        if not raw:
            return web.Response(status=404, text="no qr")
        kind = "image/png" if raw[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
        return web.Response(body=raw, content_type=kind,
                            headers={"Cache-Control": "no-store"})

    async def h_admin_qr_refresh(self, request: web.Request) -> web.Response:
        """换一张新二维码（旧的大约两分钟就过期）。"""
        self._auth(request)
        proto = self._protocol()
        if proto["kind"] != "napcat":
            return _j({"ok": True, "refresh": False,
                       "hint": f"{proto['label']} 的扫码在它自己的面板里重新登录，这里不用刷新"})
        import subprocess

        try:
            subprocess.run(["docker", "restart", "napcat"], capture_output=True, timeout=120)
        except Exception as exc:
            return _j({"ok": False, "error": f"重启协议端失败：{exc}"[:160]})
        return _j({"ok": True, "hint": "新二维码约 20 秒后生成，页面会自动刷新"})

    async def h_admin_watchdog(self, request: web.Request) -> web.Response:
        """开掉线自愈（watchdog.py，锁端口 9335）。"""
        self._auth(request)
        if self._port_open(9335):
            return _j({"ok": True, "already": True, "hint": "掉线自愈已经在跑了"})
        ok = self._spawn("watchdog.py")
        return _j({"ok": ok, "already": False,
                   "hint": "掉线自愈已开启（掉登录会自动尝试重连）" if ok else "没找到 watchdog.py"})

    async def h_admin_restart(self, request: web.Request) -> web.Response:
        """重启服务：交给独立脚本做，免得自己杀自己。"""
        self._auth(request)
        ok = self._spawn("tools/restart_bot.py")
        return _j({"ok": ok, "hint": "正在重启，约 10 秒后刷新本页" if ok else "没找到 tools/restart_bot.py"})

    async def h_admin_backup(self, request: web.Request) -> web.Response:
        """保存备份：记忆库 + 可读对话 + 配置 + 日志 → backups/*.zip"""
        self._auth(request)
        from datetime import datetime
        from pathlib import Path

        from .backup import export_backup

        dest = Path("backups") / f"qq-bridge-备份-{datetime.now():%Y%m%d-%H%M%S}.zip"
        try:
            info = await asyncio.to_thread(export_backup, Path(".").resolve(), dest)
            return _j({"ok": True, **info})
        except Exception as exc:
            return _j({"ok": False, "error": repr(exc)})
