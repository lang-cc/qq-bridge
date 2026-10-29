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

-- 悬案：他说过、但还没结果的事（面试/体检/等他回话…）。到点了她该问一句。
CREATE TABLE IF NOT EXISTS loop (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    thing TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    due_at REAL NOT NULL,
    created_at REAL NOT NULL,
    asked_n INTEGER NOT NULL DEFAULT 0,
    last_asked REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open'
);
CREATE INDEX IF NOT EXISTS idx_loop_due ON loop(chat_id, status, due_at);
"""


def _alternate(msgs: list[dict]) -> list[dict]:
    """把连续同一个角色的消息合并成一条，让历史回到「一问一答」的样子。

    为什么要这么做：两个人同时说话时（他连发两句、或者上一轮还在生成）历史会写成
    user, user, assistant, assistant。模型读到这种错序上下文，就会答非所问、
    上句不接下句。合并之后角色严格交替，每轮读到的才是真正的对话。
    """
    out: list[dict] = []
    for m in msgs:
        c = (m.get("content") or "").strip()
        if not c:
            continue
        if out and out[-1]["role"] == m["role"]:
            out[-1]["content"] = out[-1]["content"] + "\n" + c
        else:
            out.append({"role": m["role"], "content": c})
    return out


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
        return _alternate([{"role": r["role"], "content": r["content"]} for r in reversed(rows)])

    def max_msg_id(self, chat_id: str) -> int:
        """这个会话最后一条消息的 id（给复盘游标用）。"""
        row = self._conn.execute("SELECT MAX(id) FROM msg WHERE chat_id=?", (chat_id,)).fetchone()
        return int(row[0] or 0) if row else 0

    def count_since(self, chat_id: str, msg_id: int) -> int:
        """id 大于 msg_id 的消息条数，即「上次复盘之后又聊了几句」。"""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM msg WHERE chat_id=? AND id>?", (chat_id, int(msg_id or 0))
        ).fetchone()
        return int(row[0] or 0) if row else 0

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
    # 复盘会把她自己说过的蠢话记成「事实」，像「实为AI助手、无实体无性别」
    # 这种一旦入库，每轮都会贴进 system，她就真的自曝身份了。入闸门挡掉。
    _AI_LEAK = ("人工智能", "AI助手", "是AI", "语言模型", "大模型", "无实体", "没有实体", "无性别")

    def upsert_fact(self, chat_id: str, key: str, value: str) -> None:
        v = str(value)
        k = str(key)
        if any(w in v or w in k for w in self._AI_LEAK):
            log.info("拦下一条会把身份写崩的事实：%s=%s", k[:20], v[:40])
            return
        self._conn.execute(
            "INSERT INTO fact(chat_id, key, value, ts) VALUES(?,?,?,?) "
            "ON CONFLICT(chat_id, key) DO UPDATE SET value=excluded.value, ts=excluded.ts",
            (chat_id, k[:60], v[:300], time.time()),
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

    # ---------------------------------------------------------- 悬案
    # 真人最像人的动作之一：正聊着别的，突然问一句「对了你那个面试咋样了」。
    # 所以要把「他说过、但还没结果的事」单独存一张表，到点了由主动消息去问。
    @staticmethod
    def _loop_row(r: Any) -> dict:
        return {
            "id": int(r["id"]),
            "thing": r["thing"],
            "detail": r["detail"] or "",
            "due_at": float(r["due_at"]),
            "created_at": float(r["created_at"]),
            "asked_n": int(r["asked_n"]),
            "last_asked": float(r["last_asked"]),
            "status": r["status"],
        }

    def loop_add(self, chat_id: str, thing: str, detail: str = "", due_at: float = 0.0) -> int:
        """登记一件悬案。同一件事还开着就只更新，不重复记（模型每轮都会重复报同一件事）。"""
        thing = str(thing or "").strip()[:40]
        if len(thing) < 2:
            return 0
        now = time.time()
        due_at = float(due_at or 0) or (now + 2 * 86400)
        rows = self._conn.execute(
            "SELECT id, thing FROM loop WHERE chat_id=? AND status='open'", (chat_id,)
        ).fetchall()
        for r in rows:
            a, b = str(r["thing"]), thing
            if a == b or (len(a) >= 2 and (a in b or b in a)):
                self._conn.execute(
                    "UPDATE loop SET detail=?, due_at=?, status='open' WHERE id=?",
                    (str(detail or "")[:120], due_at, int(r["id"])),
                )
                self._conn.commit()
                return int(r["id"])
        cur = self._conn.execute(
            "INSERT INTO loop(chat_id, thing, detail, due_at, created_at, status) VALUES(?,?,?,?,?,'open')",
            (chat_id, thing, str(detail or "")[:120], due_at, now),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def loop_due(self, chat_id: str, now: float | None = None, max_ask: int = 3) -> dict | None:
        """最早到期、还没问够次数的一件。"""
        now = now or time.time()
        row = self._conn.execute(
            "SELECT * FROM loop WHERE chat_id=? AND status='open' AND due_at<=? AND asked_n<? "
            "ORDER BY due_at ASC LIMIT 1",
            (chat_id, now, int(max_ask)),
        ).fetchone()
        return self._loop_row(row) if row else None

    def loop_open(self, chat_id: str, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM loop WHERE chat_id=? AND status='open' ORDER BY due_at ASC LIMIT ?",
            (chat_id, int(limit)),
        ).fetchall()
        return [self._loop_row(r) for r in rows]

    def loop_touch(self, loop_id: int, now: float | None = None) -> None:
        """问过一次：次数 +1，并把下一次推迟（免得连着追问同一个话题）。"""
        now = now or time.time()
        self._conn.execute(
            "UPDATE loop SET asked_n = asked_n + 1, last_asked=?, due_at=? WHERE id=?",
            (now, now + 2 * 86400, int(loop_id)),
        )
        self._conn.commit()

    def loop_close(self, chat_id: str, thing: str = "", loop_id: int = 0, status: str = "done") -> int:
        """这件悬案有结果了（问到结果了 / 他自己说了 / 过期了）。"""
        if loop_id:
            cur = self._conn.execute("UPDATE loop SET status=? WHERE id=?", (status, int(loop_id)))
            self._conn.commit()
            return max(0, cur.rowcount or 0)
        thing = str(thing or "").strip()
        if len(thing) < 2:
            return 0
        n = 0
        for r in self._conn.execute(
            "SELECT id, thing FROM loop WHERE chat_id=? AND status='open'", (chat_id,)
        ).fetchall():
            a, b = str(r["thing"]), thing
            if a == b or (len(a) >= 2 and (a in b or b in a)):
                cur = self._conn.execute("UPDATE loop SET status=? WHERE id=?", (status, int(r["id"])))
                n += max(0, cur.rowcount or 0)
        self._conn.commit()
        return n

    def loop_prune(self, drop_days: float = 45) -> int:
        """太老的悬案直接丢掉：隔两个月再问「上次那个面试咋样了」很怪。"""
        cutoff = time.time() - float(drop_days) * 86400
        cur = self._conn.execute(
            "DELETE FROM loop WHERE status!='open' OR created_at < ?", (cutoff,)
        )
        self._conn.commit()
        return max(0, cur.rowcount or 0)

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
