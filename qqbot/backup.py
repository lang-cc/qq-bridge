"""备份导出：把记忆库、可读对话记录、配置、日志打成一个 zip。

从桌面面板（已删除）搬过来的逻辑，现在由网页配置台的「保存备份」按钮调用，
也可以命令行用：python -m qqbot.backup [输出路径]
"""

from __future__ import annotations

import logging
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

log = logging.getLogger("qqbot.backup")


def export_backup(root: Path, zip_path: Path) -> dict:
    """把 root 下的记忆/配置/日志打包到 zip_path，返回统计信息。"""
    root = Path(root)
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    info = {"db": 0, "chat_files": 0, "logs": 0, "path": str(zip_path)}

    tmpdir = Path(tempfile.mkdtemp(prefix="qqbak-"))
    personas_dir = root / "data" / "personas"
    logs_dir = root / "logs"
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for db in sorted(personas_dir.glob("*/memory.db")):
                z.write(db, f"记忆库/{db.parent.name}/memory.db")
                info["db"] += 1
                try:
                    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                    conn.row_factory = sqlite3.Row
                    chats = conn.execute(
                        "SELECT chat_id, COUNT(*) n FROM msg GROUP BY chat_id"
                    ).fetchall()
                    for row in chats:
                        chat = row["chat_id"]
                        lines = [f"# {db.parent.name} / {chat}（共 {row['n']} 条）", ""]
                        for m in conn.execute(
                            "SELECT ts, role, content FROM msg WHERE chat_id=? ORDER BY id",
                            (chat,),
                        ):
                            when = datetime.fromtimestamp(m["ts"]).strftime("%Y-%m-%d %H:%M")
                            who = "对方" if m["role"] == "user" else "机器人"
                            lines.append(f"[{when}] {who}：{m['content']}")
                        p = tmpdir / f"{db.parent.name}-{chat}.txt"
                        p.write_text("\n".join(lines), encoding="utf-8")
                        z.write(p, f"对话记录/{p.name}")
                        info["chat_files"] += 1
                    buf = [f"# {db.parent.name} 摘要与事实", ""]
                    for r in conn.execute("SELECT chat_id, text FROM summary"):
                        buf.append(f"[{r['chat_id']}] 摘要：{r['text']}")
                    for r in conn.execute("SELECT chat_id, key, value FROM fact"):
                        buf.append(f"[{r['chat_id']}] {r['key']}：{r['value']}")
                    if len(buf) > 2:
                        p = tmpdir / f"{db.parent.name}-摘要事实.txt"
                        p.write_text("\n".join(buf), encoding="utf-8")
                        z.write(p, f"对话记录/{p.name}")
                    conn.close()
                except Exception as exc:  # 单个库坏了不影响整体
                    log.warning("导出 %s 失败：%r", db, exc)

            for extra in (
                root / "data" / "personas.yaml",
                root / "data" / "usage.db",
                root / "config.yaml",
                root / "data" / "memory_router.db",
                root / "data" / "memory.db",
            ):
                if extra.exists():
                    z.write(extra, f"配置与数据/{extra.name}")

            if logs_dir.is_dir():
                for lg in sorted(
                    logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True
                )[:6]:
                    z.write(lg, f"日志/{lg.name}")
                    info["logs"] += 1
    finally:
        for f in tmpdir.glob("*"):
            try:
                f.unlink()
            except Exception:
                pass
        try:
            tmpdir.rmdir()
        except Exception:
            pass

    log.info(
        "已导出备份：%s（记忆库 %d，对话记录 %d，日志 %d）",
        zip_path,
        info["db"],
        info["chat_files"],
        info["logs"],
    )
    info["size_mb"] = round(zip_path.stat().st_size / 1e6, 2)
    return info


if __name__ == "__main__":
    import sys

    from .utils_log import setup_logging  # type: ignore

    try:
        setup_logging()
    except Exception:
        logging.basicConfig(level=logging.INFO)
    here = Path(__file__).resolve().parent.parent
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        here / "backups" / f"qq-bridge-备份-{datetime.now():%Y%m%d-%H%M%S}.zip"
    )
    print(export_backup(here, out))
