"""作废台账：文件态已作废，计划项可仍挂着。"""
from __future__ import annotations

from app.db import get_db


def record_void(file_id: int, db_path: str | None = None) -> None:
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            (f"voided_file_{file_id}", "1"),
        )


def ghost_items(plan_id: int, db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT f.* FROM plan_items i JOIN lake_files f ON f.id=i.file_id "
            "WHERE i.plan_id=? AND f.status='作废'",
            (plan_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def scrub_display_only(plan_id: int, db_path: str | None = None) -> int:
    """Half-fix: hide ghosts in detail chip, keep plan_items rows."""
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            (f"hide_ghosts_{plan_id}", "1"),
        )
        return 0
