"""长期记忆：SQLite 存对话、要点摘要、事实、心情/性格状态。

chat_id 形如 u123456（私聊）/ g7890（群）。
不用向量库：私聊量级小，靠「滚动摘要 + 关键词命中的事实 + 最近若干轮」就够用。
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("qqbot.memory")

SCHEMA = """
CREATE TABLE IF NOT EXISTS msg (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    ts REAL NOT NULL,
    keep INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_msg_chat ON msg(chat_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_msg_ts ON msg(ts);

CREATE TABLE IF NOT EXISTS summary (
    chat_id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    ts REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS fact (
    chat_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    ts REAL NOT NULL,
    PRIMARY KEY (chat_id, key)
);

CREATE TABLE IF NOT EXISTS state (
    chat_id TEXT PRIMARY KEY,
    mood TEXT NOT NULL,
    traits TEXT NOT NULL,
    ts REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS counter (
    chat_id TEXT PRIMARY KEY,
    n INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS kv (
    chat_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    ts REAL NOT NULL,
    PRIMARY KEY (chat_id, key)
);
"""


class Memory:
    def __init__(self, path: str = "data/memory.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        """老库补 keep 列：普通记忆会被定期清理，keep=1 的重要记忆永久保留。"""
        cols = [r[1] for r in self._conn.execute("PRAGMA table_info(msg)")]
        if "keep" not in cols:
            self._conn.execute("ALTER TABLE msg ADD COLUMN keep INTEGER NOT NULL DEFAULT 0")
            self._conn.commit()

    # ---------------------------------------------------------- 对话
    def add_message(self, chat_id: str, role: str, content: str) -> None:
        if not content:
            return
        self._conn.execute(
            "INSERT INTO msg(chat_id, role, content, ts) VALUES(?,?,?,?)", (chat_id, role, content, time.time())
        )
        self._conn.commit()

    def recent(self, chat_id: str, limit: int = 12) -> list[dict]:
        rows = self._conn.execute(
            "SELECT role, content FROM msg WHERE chat_id=? ORDER BY id DESC LIMIT ?", (chat_id, limit)
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def all_messages(self, chat_id: str, limit: int = 3000) -> list[dict]:
        """按 id 升序取全部消息（给语义检索用）。"""
        rows = self._conn.execute(
            "SELECT id, role, content, ts FROM msg WHERE chat_id=? ORDER BY id DESC LIMIT ?",
            (chat_id, int(limit)),
        ).fetchall()
        return [
            {"id": r["id"], "role": r["role"], "content": r["content"], "ts": r["ts"]}
            for r in reversed(rows)
        ]

    def search(self, chat_id: str, keywords: list[str], limit: int = 6, skip_recent: int = 40) -> list[dict]:
        """按关键词捞以前的旧对话，跳过最近 skip_recent 条（那些已经在上下文里了）。"""
        words = [w for w in keywords if w and len(w) >= 2][:5]
        if not words:
            return []
        liked = " OR ".join(["content LIKE ?"] * len(words))
        sql = (
            "SELECT role, content, ts FROM msg WHERE chat_id=? "
            "AND id NOT IN (SELECT id FROM msg WHERE chat_id=? ORDER BY id DESC LIMIT ?) "
            f"AND ({liked}) ORDER BY id DESC LIMIT ?"
        )
        args = [chat_id, chat_id, int(skip_recent)] + [f"%{w}%" for w in words] + [int(limit)]
        try:
            rows = self._conn.execute(sql, args).fetchall()
        except Exception:
            return []
        return [
            {"role": r["role"], "content": r["content"], "ts": r["ts"]}
            for r in reversed(rows)
        ]

    def message_count(self, chat_id: str) -> int:
        row = self._conn.execute("SELECT COUNT(*) c FROM msg WHERE chat_id=? AND role='user'", (chat_id,)).fetchone()
        return int(row["c"]) if row else 0

    def known_chats(self, limit: int = 20) -> list[str]:
        rows = self._conn.execute(
            "SELECT chat_id, MAX(ts) t FROM msg GROUP BY chat_id ORDER BY t DESC LIMIT ?", (limit,)
        ).fetchall()
        return [r["chat_id"] for r in rows]

    def last_ts(self, chat_id: str) -> float:
        row = self._conn.execute("SELECT MAX(ts) t FROM msg WHERE chat_id=?", (chat_id,)).fetchone()
        return float(row["t"] or 0) if row else 0.0

    # ---------------------------------------------------------- 摘要
    def get_summary(self, chat_id: str) -> str:
        row = self._conn.execute("SELECT text FROM summary WHERE chat_id=?", (chat_id,)).fetchone()
        return row["text"] if row else ""

    def set_summary(self, chat_id: str, text: str) -> None:
        self._conn.execute(
            "INSERT INTO summary(chat_id, text, ts) VALUES(?,?,?) "
            "ON CONFLICT(chat_id) DO UPDATE SET text=excluded.text, ts=excluded.ts",
            (chat_id, text, time.time()),
        )
        self._conn.commit()

    # ---------------------------------------------------------- 事实
    def upsert_fact(self, chat_id: str, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO fact(chat_id, key, value, ts) VALUES(?,?,?,?) "
            "ON CONFLICT(chat_id, key) DO UPDATE SET value=excluded.value, ts=excluded.ts",
            (chat_id, str(key)[:60], str(value)[:300], time.time()),
        )
        self._conn.commit()

    def facts(self, chat_id: str, limit: int = 24) -> dict[str, str]:
        rows = self._conn.execute(
            "SELECT key, value FROM fact WHERE chat_id=? ORDER BY ts DESC LIMIT ?", (chat_id, limit)
        ).fetchall()
        return {r["key"]: r["value"] for r in rows}

    def forget(self, chat_id: str) -> None:
        for t in ("msg", "summary", "fact", "state", "counter"):
            self._conn.execute(f"DELETE FROM {t} WHERE chat_id=?", (chat_id,))
        self._conn.commit()

    # ---------------------------------------------------------- 状态（心情/性格）
    def get_state(self, chat_id: str) -> dict[str, Any]:
        row = self._conn.execute("SELECT mood, traits FROM state WHERE chat_id=?", (chat_id,)).fetchone()
        if not row:
            return {"mood": {}, "traits": {}}
        try:
            return {"mood": json.loads(row["mood"] or "{}"), "traits": json.loads(row["traits"] or "{}")}
        except Exception:
            return {"mood": {}, "traits": {}}

    def set_state(self, chat_id: str, mood: dict, traits: dict) -> None:
        self._conn.execute(
            "INSERT INTO state(chat_id, mood, traits, ts) VALUES(?,?,?,?) "
            "ON CONFLICT(chat_id) DO UPDATE SET mood=excluded.mood, traits=excluded.traits, ts=excluded.ts",
            (chat_id, json.dumps(mood, ensure_ascii=False), json.dumps(traits, ensure_ascii=False), time.time()),
        )
        self._conn.commit()

    # ---------------------------------------------------------- 杂项键值
    def kv_get(self, chat_id: str, key: str, default: Any = None) -> Any:
        row = self._conn.execute("SELECT value FROM kv WHERE chat_id=? AND key=?", (chat_id, key)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except Exception:
            return default

    def kv_set(self, chat_id: str, key: str, value: Any) -> None:
        self._conn.execute(
            "INSERT INTO kv(chat_id, key, value, ts) VALUES(?,?,?,?) "
            "ON CONFLICT(chat_id, key) DO UPDATE SET value=excluded.value, ts=excluded.ts",
            (chat_id, key, json.dumps(value, ensure_ascii=False), time.time()),
        )
        self._conn.commit()

    # ---------------------------------------------------------- 计数
    def bump_counter(self, chat_id: str) -> int:
        self._conn.execute(
            "INSERT INTO counter(chat_id, n) VALUES(?, 1) ON CONFLICT(chat_id) DO UPDATE SET n = n + 1",
            (chat_id,),
        )
        self._conn.commit()
        row = self._conn.execute("SELECT n FROM counter WHERE chat_id=?", (chat_id,)).fetchone()
        return int(row["n"]) if row else 1

    def reset_counter(self, chat_id: str) -> None:
        self._conn.execute("DELETE FROM counter WHERE chat_id=?", (chat_id,))
        self._conn.commit()

    # ---------------------------------------------------------- 记忆保留策略
    def mark_keep(self, chat_id: str, phrases: list[str]) -> int:
        """把含重要原话的消息标记为永久保留。"""
        n = 0
        for ph in phrases or []:
            ph = str(ph).strip()
            if len(ph) < 4:
                continue
            cur = self._conn.execute(
                "UPDATE msg SET keep=1 WHERE chat_id=? AND keep=0 AND content LIKE ?",
                (chat_id, f"%{ph[:40]}%"),
            )
            n += max(0, cur.rowcount or 0)
        self._conn.commit()
        return n

    def prune(self, retain_days: float) -> int:
        """删掉超过保留期的普通消息；keep=1 的一律不动。"""
        cutoff = time.time() - float(retain_days) * 86400
        cur = self._conn.execute("DELETE FROM msg WHERE ts < ? AND keep = 0", (cutoff,))
        self._conn.commit()
        return max(0, cur.rowcount or 0)

    def stats(self, chat_id: str) -> dict:
        row = self._conn.execute(
            "SELECT COUNT(*) total, SUM(keep) kept, MIN(ts) oldest FROM msg WHERE chat_id=?", (chat_id,)
        ).fetchone()
        oldest = float(row["oldest"] or 0) if row else 0.0
        return {
            "total": int(row["total"] or 0) if row else 0,
            "kept": int(row["kept"] or 0) if row else 0,
            "oldest_days": round((time.time() - oldest) / 86400, 1) if oldest else 0,
        }

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
