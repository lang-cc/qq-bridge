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
from typing import Any

from aiohttp import web

from . import message as msg

log = logging.getLogger("qqbot.http_api")


def _j(data: Any, status: int = 200) -> web.Response:
    """返回 JSON，中文不转义。"""
    return web.Response(
        body=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        status=status,
        content_type="application/json",
    )


class HttpApi:
    def __init__(self, bot: Any, cfg: dict | None = None) -> None:
        self.bot = bot
        self.cfg = cfg or {}
        self.host = str(self.cfg.get("host") or "127.0.0.1")
        self.port = int(self.cfg.get("port") or 8088)
        self.token = str(self.cfg.get("token") or "")
        self._runner: Any = None

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
                web.post("/admin/reload", self.h_admin_reload),
                web.post("/admin/share", self.h_admin_share),
                web.post("/admin/diary", self.h_admin_diary),
                web.post("/admin/image", self.h_admin_image),
                web.get("/admin/usage", self.h_admin_usage),
            ]
        )
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
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
    async def h_status(self, request: web.Request) -> web.Response:
        self._auth(request)
        return _j(
            {
                "ok": True,
                "adapter": self.bot.adapter.name,
                "self_id": self.bot.self_id,
                "connected": getattr(self.bot.adapter, "_ws", None) is not None,
                "plugins": len(self.bot.router.handlers),
            }
        )

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
        from .admin import PAGE

        return web.Response(text=PAGE, content_type="text/html", charset="utf-8")

    async def h_admin_config(self, request: web.Request) -> web.Response:
        return _j({"autoreply": self._raw().get("autoreply") or {}})

    async def h_admin_save(self, request: web.Request) -> web.Response:
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
        from .admin import list_models

        return _j(await list_models(self._raw().get("autoreply") or {}))

    async def h_admin_test(self, request: web.Request) -> web.Response:
        from .admin import test_llm

        data = await self._body(request)
        autoreply = data.get("autoreply") or self._raw().get("autoreply") or {}
        return _j(await test_llm(autoreply, data.get("text") or "在吗"))

    async def h_admin_reload(self, request: web.Request) -> web.Response:
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
