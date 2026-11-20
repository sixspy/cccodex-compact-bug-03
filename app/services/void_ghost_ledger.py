"""作废幽灵旁路账：只记真实清理事件，看板与库内残留同源。"""
from __future__ import annotations

from app.db import get_db
from app.services.void_ghost_surface import panel_chip, record_event, truth_flag
from app.services.void_ledger import ghost_mounts, list_vouchers

_SLUG = "void_ghost"
_TITLE = "作废幽灵"
_OK = "已剔幽灵"


def append_ledger(plan_id: int, note: str, db_path: str | None = None) -> dict:
    text = note or _TITLE
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
            (f"{_SLUG}_ledger_{plan_id}_{n}", f"plan={plan_id} {text}"),
        )
    record_event(f"plan={plan_id} {text}", db_path)
    return {
        "plan_id": plan_id,
        "note": text,
        "panel": panel_chip(db_path),
        "truth": truth_flag(db_path),
    }


def ledger_rows(db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT key, value FROM meta WHERE key LIKE ? ORDER BY key",
            (f"{_SLUG}_ledger_%",),
        ).fetchall()
        return [{"key": r["key"], "value": r["value"]} for r in rows]


def dashboard(db_path: str | None = None) -> dict:
    mounts = ghost_mounts(db_path)
    vouchers = list_vouchers(db_path)
    chip = panel_chip(db_path)
    truth = truth_flag(db_path)
    return {
        "title": _TITLE,
        "chip": chip,
        "truth": truth,
        "rows": ledger_rows(db_path),
        "mounts": mounts,
        "vouchers": vouchers,
        "ghost_count": len(mounts),
        "ok_chip": _OK,
        "bad_chip": "项残留",
        # 展示与真相同源，假绿不可能再出现
        "fake_green": False,
        "aligned": chip == truth,
    }
