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
import sys
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
                web.post("/admin/reload", self.h_admin_reload),
                web.post("/admin/share", self.h_admin_share),
                web.post("/admin/diary", self.h_admin_diary),
                web.post("/admin/image", self.h_admin_image),
                web.get("/admin/usage", self.h_admin_usage),
                web.get("/admin/logs", self.h_admin_logs),
                web.get("/admin/memory", self.h_admin_memory),
                web.post("/admin/memory/clear", self.h_admin_memory_clear),
                web.post("/admin/login", self.h_admin_login),
                web.post("/admin/watchdog", self.h_admin_watchdog),
                web.post("/admin/restart", self.h_admin_restart),
                web.post("/admin/backup", self.h_admin_backup),
                web.get("/admin/plugins", self.h_admin_plugins),
                web.post("/admin/plugins/toggle", self.h_admin_plugin_toggle),
                web.get("/admin/features", self.h_admin_features),
                web.get("/admin/napcat", self.h_admin_napcat),
                web.post("/admin/features/toggle", self.h_admin_feature_toggle),
            ]
        )
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
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

    async def h_admin_napcat(self, request: web.Request) -> web.Response:
        """NapCat 面板地址 + 密码（网页配置台主页上要给用户看）。"""
        self._auth(request)
        import json
        from pathlib import Path as _P

        info = {"ok": True, "port": 6099, "token": "", "url": "http://127.0.0.1:6099", "webui": ""}
        for rel in ("napcat/config/webui.json", "napcat/webui.json"):
            f = _P(rel)
            if not f.exists():
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception as exc:
                return _j({"ok": False, "error": "读不了 %s：%r" % (rel, exc)})
            port = int(data.get("port") or 6099)
            token = str(data.get("token") or "")
            info.update({
                "port": port,
                "token": token,
                "url": "http://127.0.0.1:%d" % port,
                "webui": "http://127.0.0.1:%d/webui?token=%s" % (port, token) if token
                         else "http://127.0.0.1:%d/webui" % port,
                "file": rel,
            })
            break
        return _j(info)

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
                chats = []
                for pid, path in files:
                    mem = Memory(str(path))
                    for cid in mem.known_chats(limit=50):
                        chats.append({"persona": pid, "chat": cid,
                                      "count": mem.message_count(cid)})
                chats.sort(key=lambda c: c["count"], reverse=True)
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
        for pid, path in files:
            if persona and pid != persona:
                continue
            try:
                mem = Memory(str(path))
                if mem.message_count(chat) > 0:
                    mem.forget(chat)
                    return _j({"ok": True, "persona": pid, "chat": chat})
            except Exception as exc:
                return _j({"ok": False, "error": repr(exc)})
        return _j({"ok": False, "error": f"没找到 {chat} 的记忆"})

    # ---------------------------------------------------------------- 动作按钮
    # 桌面面板删掉之后，扫码登录 / 掉线自愈 / 重启 / 备份 都收到网页配置台上。
    @staticmethod
    def _python_exe(windowless: bool = True):
        """优先用 .venv 里的 python（pythonw 无窗口）。"""
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        cand = root / ".venv" / "Scripts" / ("pythonw.exe" if windowless else "python.exe")
        if cand.exists():
            return str(cand)
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

    async def h_admin_login(self, request: web.Request) -> web.Response:
        """拉起扫码登录窗口（QQ 协议端登录）。"""
        self._auth(request)
        ok = self._spawn("login_qr.py")
        return _j({"ok": ok, "hint": "扫码窗口已弹出，用手机 QQ 扫一下" if ok else "没找到 login_qr.py"})

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
