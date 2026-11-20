"""作废台账与幽灵清理（彻清路线，唯一真相源）。

规则：
- 文件作废即生成作废凭证（void_vouchers），计划项暂留形成幽灵挂载；
- 幽灵清理在同一事务、同一写锁内：记撤销凭证 -> 删 plan_items 挂载行；
- 清理后字节与卡片立刻剔除幽灵；幽灵项不得再进入合并可选项；
- 只刷展示不删挂载行的半修入口已移除。
"""
from __future__ import annotations

from datetime import datetime

from app.db import get_db
from app.services.errors import ServiceError


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def record_void(
    file_id: int,
    db_path: str | None = None,
    conn=None,
) -> dict:
    """作废时写凭证：每个碎文件一份，未清理状态。

    传入 conn 时复用外层事务（作废与凭证必须同提交）。
    """
    if conn is not None:
        return _insert_voucher(conn, file_id)
    with get_db(db_path) as own:
        return _insert_voucher(own, file_id)


def _insert_voucher(conn, file_id: int) -> dict:
    file_row = conn.execute(
        "SELECT * FROM lake_files WHERE id=?", (file_id,)
    ).fetchone()
    if not file_row:
        raise ServiceError("文件不存在", 404)
    plan_row = conn.execute(
        "SELECT plan_id FROM plan_items WHERE file_id=? ORDER BY plan_id LIMIT 1",
        (file_id,),
    ).fetchone()
    plan_id = plan_row["plan_id"] if plan_row else None
    existing = conn.execute(
        "SELECT id FROM void_vouchers WHERE file_id=? AND revoked_at IS NULL",
        (file_id,),
    ).fetchone()
    if existing:
        return dict(
            conn.execute(
                "SELECT * FROM void_vouchers WHERE id=?", (existing["id"],)
            ).fetchone()
        )
    cur = conn.execute(
        "INSERT INTO void_vouchers(file_id, plan_id, path, size_bytes, voided_at) "
        "VALUES (?,?,?,?,?)",
        (
            file_id,
            plan_id,
            file_row["path"],
            int(file_row["size_bytes"]),
            _now(),
        ),
    )
    return dict(
        conn.execute(
            "SELECT * FROM void_vouchers WHERE id=?", (cur.lastrowid,)
        ).fetchone()
    )


def ghost_items(
    plan_id: int,
    db_path: str | None = None,
    conn=None,
) -> list[dict]:
    """计划内的幽灵挂载：plan_items 仍在、文件已作废。"""
    if conn is not None:
        rows = conn.execute(
            "SELECT f.* FROM plan_items i JOIN lake_files f ON f.id=i.file_id "
            "WHERE i.plan_id=? AND f.status='作废' ORDER BY f.id",
            (plan_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    with get_db(db_path) as own:
        rows = own.execute(
            "SELECT f.* FROM plan_items i JOIN lake_files f ON f.id=i.file_id "
            "WHERE i.plan_id=? AND f.status='作废' ORDER BY f.id",
            (plan_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def ghost_mounts(db_path: str | None = None) -> list[dict]:
    """全库幽灵挂载（跨所有计划），供清理与看板共用。"""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT i.plan_id AS plan_id, i.file_id AS file_id, "
            "f.path AS path, f.size_bytes AS size_bytes, p.plan_code AS plan_code "
            "FROM plan_items i "
            "JOIN lake_files f ON f.id=i.file_id "
            "JOIN compact_plans p ON p.id=i.plan_id "
            "WHERE f.status='作废' ORDER BY i.plan_id, i.file_id"
        ).fetchall()
        return [dict(r) for r in rows]


def ghost_count(plan_id: int | None = None, db_path: str | None = None) -> int:
    with get_db(db_path) as conn:
        if plan_id is None:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM plan_items i "
                "JOIN lake_files f ON f.id=i.file_id WHERE f.status='作废'"
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM plan_items i "
                "JOIN lake_files f ON f.id=i.file_id "
                "WHERE i.plan_id=? AND f.status='作废'",
                (plan_id,),
            ).fetchone()
        return int(row["c"])


def list_vouchers(db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM void_vouchers ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]


def purge_ghosts(
    file_id: int | None = None, db_path: str | None = None
) -> dict:
    """服务端一次写完的幽灵清理。

    BEGIN IMMEDIATE 先取写锁：两侧仓管并发清理时只有一侧能进入临界区，
    另一侧等待后拿到锁时挂载行已不存在，自然变成幂等空操作，
    不会出现双成功互相覆盖。
    """
    note = "仓管清理幽灵挂载"
    with get_db(db_path) as conn:
        conn.isolation_level = None  # 切 autocommit，事务边界完全显式
        conn.execute("BEGIN IMMEDIATE")
        try:
            mounts = conn.execute(
                "SELECT i.plan_id AS plan_id, i.file_id AS file_id "
                "FROM plan_items i JOIN lake_files f ON f.id=i.file_id "
                "WHERE f.status='作废'"
                + (" AND i.file_id=?" if file_id is not None else ""),
                (file_id,) if file_id is not None else (),
            ).fetchall()
            removed = 0
            plan_ids: set[int] = set()
            for m in mounts:
                conn.execute(
                    "UPDATE void_vouchers SET revoked_at=?, revoke_note=? "
                    "WHERE file_id=? AND revoked_at IS NULL",
                    (_now(), note, m["file_id"]),
                )
                conn.execute(
                    "DELETE FROM plan_items WHERE plan_id=? AND file_id=?",
                    (m["plan_id"], m["file_id"]),
                )
                removed += 1
                plan_ids.add(int(m["plan_id"]))
            remaining = conn.execute(
                "SELECT COUNT(*) AS c FROM plan_items i "
                "JOIN lake_files f ON f.id=i.file_id WHERE f.status='作废'"
            ).fetchone()["c"]
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return {
            "removed": removed,
            "plan_ids": sorted(plan_ids),
            "remaining_ghosts": int(remaining),
        }
