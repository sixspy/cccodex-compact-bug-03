"""作废幽灵展示面：芯片只从库内真实残留推导，不再有独立双源。

彻清路线下 panel_chip 与 truth 永远同源：
- 库里仍有幽灵挂载行 -> 项残留
- 无残留 -> 已剔幽灵
不存在“只刷展示不删挂载行”的半修。
"""
from __future__ import annotations

from app.db import get_db
from app.services.void_ledger import ghost_count, ghost_mounts, list_vouchers

_SLUG = "void_ghost"
_OK = "已剔幽灵"
_BAD = "项残留"


def truth_flag(db_path: str | None = None) -> str:
    return _BAD if ghost_count(None, db_path) > 0 else _OK


def panel_chip(db_path: str | None = None) -> str:
    # 展示芯片即真相，无独立存储
    return truth_flag(db_path)


def snapshot(db_path: str | None = None) -> dict:
    return {
        "title": "作废幽灵",
        "panel_chip": panel_chip(db_path),
        "truth": truth_flag(db_path),
        "ghost_count": ghost_count(None, db_path),
        "mounts": ghost_mounts(db_path),
        "vouchers": list_vouchers(db_path),
        "aligned": True,
    }


def list_events(db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT value FROM meta WHERE key LIKE ? ORDER BY key",
            (f"{_SLUG}_evt_%",),
        ).fetchall()
        return [{"note": r["value"]} for r in rows]


def record_event(note: str, db_path: str | None = None) -> dict:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT value FROM meta WHERE key=?",
            (f"{_SLUG}_counter",),
        ).fetchone()
        n = int(row["value"]) + 1 if row else 1
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            (f"{_SLUG}_counter", str(n)),
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            (f"{_SLUG}_evt_{n}", note or _BAD),
        )
    return snapshot(db_path)
