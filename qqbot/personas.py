"""多重人格 + 记忆备份。

每个人格有：
  - 独立记忆库 data/personas/<id>/memory.db（对话/摘要/事实/心情/性格全隔离）
  - 自己的人设 prompt（data/personas.yaml）
  - 每个会话固定绑一个人格（data/memory_router.db）：第一次说话时自动绑定，之后不可在聊天里切换

备份：
  - backup() 走 SQLite 在线备份（不锁库、不丢事务），存 data/backups/
  - 保留最近 keep 份，按人格分别滚动
  - restore() 先给当前库做一次安全备份，再覆盖，避免「恢复错文件把记忆彻底弄没」
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import time
from pathlib import Path

import yaml

log = logging.getLogger("qqbot.personas")

DEFAULT_PERSONAS = {
    "active": "xiaobei",
    "personas": [
        {
            "id": "xiaobei",
            "name": "小北",
            "prompt": (
                "你是小北，24 岁男生，做设计，话不多但挺会接话，爱打游戏和看番。"
                "说话随意、偶尔贫嘴，不用书面语，不主动示好但也不冷淡。"
            ),
        },
        {
            "id": "atang",
            "name": "阿糖",
            "prompt": (
                "你是阿糖，21 岁女生，学生，话多、爱撒娇、爱用语气词哈哈哈。"
                "喜欢分享日常小事和好吃的，遇到有趣的事会连发两条。"
            ),
        },
    ],
}


class PersonaStore:
    def __init__(self, root: str = "data") -> None:
        self.root = Path(root)
        self.pdir = self.root / "personas"
        self.bdir = self.root / "backups"
        self.yaml_path = self.root / "personas.yaml"
        self.router_path = self.root / "memory_router.db"
        self.pdir.mkdir(parents=True, exist_ok=True)
        self.bdir.mkdir(parents=True, exist_ok=True)
        self._mems: dict[str, object] = {}
        self._ensure_defaults()

    # ---------------------------------------------------------- 人格定义
    def _ensure_defaults(self) -> None:
        if not self.yaml_path.exists():
            self.yaml_path.write_text(
                yaml.safe_dump(DEFAULT_PERSONAS, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            log.info("已生成默认人格：%s", self.yaml_path)
        data = self.load()
        if not data.get("personas"):
            data = DEFAULT_PERSONAS
            self.save(data)

    def load(self) -> dict:
        try:
            data = yaml.safe_load(self.yaml_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            log.error("读取 personas.yaml 失败：%r", exc)
            return dict(DEFAULT_PERSONAS)
        data.setdefault("personas", [])
        if not data.get("active") and data["personas"]:
            data["active"] = data["personas"][0]["id"]
        return data

    def save(self, data: dict) -> None:
        self.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def personas(self) -> list[dict]:
        return self.load().get("personas") or []

    def get(self, pid: str) -> dict | None:
        for p in self.personas():
            if p.get("id") == pid:
                return p
        return None

    def find_by_name(self, name: str) -> dict | None:
        for p in self.personas():
            if p.get("name") == name or p.get("id") == name:
                return p
        return None

    def active_id(self) -> str:
        data = self.load()
        pid = data.get("active")
        if pid and self.get(pid):
            return pid
        plist = data.get("personas") or []
        return plist[0]["id"] if plist else "default"

    def set_active(self, pid: str) -> bool:
        data = self.load()
        if not self.get(pid):
            return False
        data["active"] = pid
        self.save(data)
        return True

    # ---------------------------------------------------------- 记忆库
    def memory_path(self, pid: str) -> Path:
        d = self.pdir / pid
        d.mkdir(parents=True, exist_ok=True)
        return d / "memory.db"

    def memory(self, pid: str):
        if pid not in self._mems:
            from .memory import Memory

            self._mems[pid] = Memory(str(self.memory_path(pid)))
        return self._mems[pid]

    # ---------------------------------------------------------- 会话 -> 人格
    def _router(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.router_path), check_same_thread=False)
        conn.execute("CREATE TABLE IF NOT EXISTS route (chat_id TEXT PRIMARY KEY, persona TEXT NOT NULL, ts REAL)")
        conn.commit()
        return conn

    def chat_persona(self, chat_id: str) -> str:
        """这个会话用哪个人格：第一次见到就定下来，之后永久固定。

        一个号只对应一个人格（不能自己在聊天里换）。没绑定过的会话，
        第一次说话时自动绑到「默认人格」（active），绑定关系写进 memory_router.db，
        以后改人设文本可以，但不会换人。
        """
        with self._router() as conn:
            row = conn.execute("SELECT persona FROM route WHERE chat_id=?", (chat_id,)).fetchone()
        pid = row[0] if row else None
        if pid and self.get(pid):
            return pid
        target = self.active_id()
        if not self.get(target):
            ps = self.personas()
            target = ps[0]["id"] if ps else target
        try:
            self.bind_persona(chat_id, target)
            log.info("新会话绑定人格：%s → %s（之后固定，不再变）", chat_id, target)
        except Exception as exc:
            log.warning("绑定人格失败：%r", exc)
        return target

    def bind_persona(self, chat_id: str, pid: str) -> bool:
        """把会话绑定到某个人格。只给装机脚本 / 后台用 —— 聊天里已经没有切换入口了。"""
        if not self.get(pid):
            return False
        with self._router() as conn:
            conn.execute(
                "INSERT INTO route(chat_id, persona, ts) VALUES(?,?,?) "
                "ON CONFLICT(chat_id) DO UPDATE SET persona=excluded.persona, ts=excluded.ts",
                (chat_id, pid, time.time()),
            )
            conn.commit()
        return True

    # ---------------------------------------------------------- 备份
    def backup(self, pid: str | None = None, keep: int = 20) -> list[str]:
        pids = [pid] if pid else [p["id"] for p in self.personas()]
        made: list[str] = []
        for one in pids:
            src_path = self.memory_path(one)
            if not src_path.exists() or src_path.stat().st_size == 0:
                continue
            stamp = time.strftime("%Y%m%d-%H%M%S")
            dst_path = self.bdir / f"{one}-{stamp}.db"
            try:
                src = sqlite3.connect(str(src_path))
                dst = sqlite3.connect(str(dst_path))
                with dst:
                    src.backup(dst)
                src.close()
                dst.close()
                made.append(str(dst_path))
                log.info("记忆已备份：%s", dst_path.name)
            except Exception as exc:
                log.error("备份 %s 失败：%r", one, exc)
        self._prune(keep)
        return made

    def _prune(self, keep: int) -> None:
        by_pid: dict[str, list[Path]] = {}
        for f in self.bdir.glob("*.db"):
            pid = f.name.split("-")[0]
            by_pid.setdefault(pid, []).append(f)
        for pid, files in by_pid.items():
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            for old in files[max(1, keep) :]:
                try:
                    old.unlink()
                except Exception:
                    pass

    def backups(self) -> list[dict]:
        out = []
        for f in sorted(self.bdir.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True):
            pid = f.name.split("-")[0]
            persona = self.get(pid)
            out.append(
                {
                    "file": f.name,
                    "persona": pid,
                    "persona_name": (persona or {}).get("name", pid),
                    "size": f.stat().st_size,
                    "time": f.stat().st_mtime,
                }
            )
        return out

    def restore(self, filename: str) -> dict:
        src = self.bdir / filename
        if not src.exists():
            return {"ok": False, "error": "备份不存在"}
        pid = filename.split("-")[0]
        if not self.get(pid):
            return {"ok": False, "error": f"找不到人格 {pid}"}
        target = self.memory_path(pid)
        try:
            if target.exists():
                safety = self.bdir / f"{pid}-before-restore-{time.strftime('%Y%m%d-%H%M%S')}.db"
                shutil.copyfile(target, safety)
            # 关掉缓存的连接，避免覆盖后被旧句柄写脏
            mem = self._mems.pop(pid, None)
            if mem is not None:
                try:
                    mem.close()
                except Exception:
                    pass
            shutil.copyfile(src, target)
            return {"ok": True, "persona": pid}
        except Exception as exc:
            return {"ok": False, "error": repr(exc)}
