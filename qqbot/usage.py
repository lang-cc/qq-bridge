"""用量统计：每次模型调用记一笔 tokens，随时看花了多少。

单价（元/百万 tokens）在 config.yaml 的 autoreply.usage 里配，默认按中转站常见价位估。
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

log = logging.getLogger("qqbot.usage")

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    day TEXT NOT NULL,
    kind TEXT NOT NULL,
    persona TEXT,
    chat_id TEXT,
    model TEXT,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    cost REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_usage_day ON usage(day);
CREATE INDEX IF NOT EXISTS idx_usage_kind ON usage(kind);
"""

DEFAULT_PRICE_IN = 1.0   # 元 / 百万 输入 tokens
DEFAULT_PRICE_OUT = 2.0  # 元 / 百万 输出 tokens


class Usage:
    def __init__(self, db: str | Path = "data/usage.db") -> None:
        path = Path(db)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def record(self, kind: str, model: str = "", usage: dict | None = None, persona: str = "", chat_id: str = "",
               price_in: float = DEFAULT_PRICE_IN, price_out: float = DEFAULT_PRICE_OUT) -> None:
        u = usage or {}
        p = int(u.get("prompt_tokens") or 0)
        c = int(u.get("completion_tokens") or 0)
        t = int(u.get("total_tokens") or (p + c))
        if t <= 0 and p <= 0 and c <= 0:
            return
        cost = (p / 1_000_000) * float(price_in) + (c / 1_000_000) * float(price_out)
        now = time.time()
        try:
            self._conn.execute(
                "INSERT INTO usage(ts, day, kind, persona, chat_id, model, prompt_tokens, completion_tokens, total_tokens, cost) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (now, time.strftime("%Y-%m-%d", time.localtime(now)), kind, persona, chat_id, model, p, c, t, cost),
            )
            self._conn.commit()
        except Exception as exc:
            log.warning("用量记录失败：%r", exc)

    def summary(self, days: int = 1, persona: str = "") -> dict:
        since = time.strftime("%Y-%m-%d", time.localtime(time.time() - (days - 1) * 86400))
        where = "day >= ?" + (" AND persona = ?" if persona else "")
        args = (since, persona) if persona else (since,)
        row = self._conn.execute(
            f"SELECT COUNT(*) calls, SUM(total_tokens) tokens, SUM(prompt_tokens) pin, "
            f"SUM(completion_tokens) pout, SUM(cost) cost FROM usage WHERE {where}",
            args,
        ).fetchone()
        kinds = self._conn.execute(
            f"SELECT kind, COUNT(*) calls, SUM(total_tokens) tokens, SUM(cost) cost FROM usage WHERE {where} "
            f"GROUP BY kind ORDER BY tokens DESC",
            args,
        ).fetchall()
        people = self._conn.execute(
            f"SELECT persona, COUNT(*) calls, SUM(total_tokens) tokens, SUM(cost) cost FROM usage WHERE {where} "
            f"GROUP BY persona ORDER BY tokens DESC",
            args,
        ).fetchall()
        return {
            "days": days,
            "calls": int(row["calls"] or 0) if row else 0,
            "tokens": int(row["tokens"] or 0) if row else 0,
            "prompt_tokens": int(row["pin"] or 0) if row else 0,
            "completion_tokens": int(row["pout"] or 0) if row else 0,
            "cost": round(float(row["cost"] or 0), 4) if row else 0.0,
            "by_kind": [dict(k) for k in kinds],
            "by_persona": [dict(p) for p in people],
        }

    def close(self) -> None:
        self._conn.close()
