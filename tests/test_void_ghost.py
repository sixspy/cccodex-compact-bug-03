"""compact-bug-03 第三号专属核验：作废幽灵彻清。

四块同检（碎件列表 / 计划卡片 / 合并详情 / 对账目录）+ 账册与库表双查。
"""
from __future__ import annotations

import threading

import pytest

from app.db import get_db
from app.seed import reset_seed
from app.services import files, plans, reconcile, rewrite
from app.services.errors import ServiceError
from app.services.void_ghost_ledger import dashboard
from app.services.void_ledger import (
    ghost_count,
    ghost_items,
    ghost_mounts,
    list_vouchers,
    purge_ghosts,
)
from app.services.void_ghost_surface import snapshot


def _first_attached(db):
    return next(x for x in files.list_files(db_path=db) if x["status"] == "已入计划")


# ---------- 甲：碎件列表（作废态 + 幽灵标记） ----------

def test_void_writes_voucher_and_list_shows_void_state(db):
    f = _first_attached(db)
    out = files.void_file(f["id"], db_path=db)
    assert out["status"] == "作废"
    listing = {x["id"]: x for x in files.list_files(db_path=db)}
    row = listing[f["id"]]
    assert row["status"] == "作废"
    assert row["ghost_mount"] == 1  # 挂载行仍在 -> 幽灵
    vouchers = list_vouchers(db)
    assert len(vouchers) == 1
    v = vouchers[0]
    assert v["file_id"] == f["id"]
    assert v["path"] == f["path"]
    assert v["size_bytes"] == f["size_bytes"]
    assert v["voided_at"]
    assert v["revoked_at"] is None  # 清理前不允许写撤销时间


def test_void_is_idempotent_single_open_voucher(db):
    f = _first_attached(db)
    files.void_file(f["id"], db_path=db)
    files.void_file(f["id"], db_path=db)
    open_vouchers = [v for v in list_vouchers(db) if v["revoked_at"] is None]
    assert len(open_vouchers) == 1


# ---------- 乙：计划卡片（芯片与字节对齐真相） ----------

def test_plan_card_chip_and_bytes_reflect_ghost(db):
    plan = plans.list_plans(db_path=db)[0]
    original_bytes = int(plan["plan_bytes"])
    f = _first_attached(db)
    files.void_file(f["id"], db_path=db)

    card = next(p for p in plans.list_plans(db_path=db) if p["id"] == plan["id"])
    assert card["ghost_count"] == 1
    # 戊：总字节立刻剔幽灵
    assert card["plan_bytes"] == original_bytes - f["size_bytes"]

    detail = plans.plan_detail(plan["id"], db_path=db)
    # 庚(作废态) 与 辛(计划项) 对齐检查：偏了 -> 芯片必须是“项残留”
    assert detail["plan_chip"] == "项残留"
    assert detail["ghost_count"] == 1
    assert detail["clean_bytes"] == original_bytes - f["size_bytes"]
    assert any(g["id"] == f["id"] for g in detail["ghost_items"])


def test_plan_card_chip_turns_ok_only_after_real_purge(db):
    plan = plans.list_plans(db_path=db)[0]
    f = _first_attached(db)
    files.void_file(f["id"], db_path=db)
    assert plans.plan_detail(plan["id"], db_path=db)["plan_chip"] == "项残留"

    purge_ghosts(db_path=db)
    detail = plans.plan_detail(plan["id"], db_path=db)
    assert detail["plan_chip"] == "已剔幽灵"
    assert detail["ghost_count"] == 0
    card = next(p for p in plans.list_plans(db_path=db) if p["id"] == plan["id"])
    assert card["ghost_count"] == 0
    # 挂载行确实删除，而非仅展示隐藏
    with get_db(db) as conn:
        left = conn.execute(
            "SELECT COUNT(*) AS c FROM plan_items WHERE file_id=?", (f["id"],)
        ).fetchone()["c"]
    assert left == 0


# ---------- 丙：合并详情（幽灵不得进入合并可选项） ----------

def test_ghost_cannot_enter_merge_options_or_start(db):
    plan = plans.list_plans(db_path=db)[0]
    plans.publish_plan(plan["id"], db_path=db)
    f = _first_attached(db)
    files.void_file(f["id"], db_path=db)

    # 辰巳：幽灵项不得再进入合并可选项/启动
    with pytest.raises(ServiceError) as ei:
        rewrite.start_rewrite(plan["id"], db_path=db)
    assert ei.value.status_code == 409
    assert "幽灵" in ei.value.message

    with get_db(db) as conn:
        jobs = conn.execute("SELECT COUNT(*) AS c FROM rewrite_jobs").fetchone()["c"]
    assert jobs == 0
    # 作废文件状态没有被合并任务吞成“已合并”
    refreshed = next(x for x in files.list_files(db_path=db) if x["id"] == f["id"])
    assert refreshed["status"] == "作废"


def test_merge_succeeds_after_purge_and_skips_no_ghost(db):
    plan = plans.list_plans(db_path=db)[0]
    plans.publish_plan(plan["id"], db_path=db)
    f = _first_attached(db)
    files.void_file(f["id"], db_path=db)
    purge_ghosts(db_path=db)

    job = rewrite.start_rewrite(plan["id"], db_path=db)
    assert job["status"] == "成功"
    # 合并字节不含已作废碎件
    survivors = [
        x
        for x in files.list_files(db_path=db)
        if x["table_name"] == plan["target_table"] and x["status"] == "已合并"
    ]
    assert all(x["id"] != f["id"] for x in survivors)
    assert job["merged_bytes"] == sum(x["size_bytes"] for x in survivors)


def test_reattach_never_picks_voided_file(db):
    plan = plans.list_plans(db_path=db)[0]
    f = _first_attached(db)
    files.void_file(f["id"], db_path=db)
    purge_ghosts(db_path=db)
    # 再挂也只能捞 status='碎文件'，作废文件回不来
    attached = plans.attach_loose_files(plan["id"], db_path=db)
    assert attached["attached"] == 0
    assert ghost_count(plan["id"], db) == 0


# ---------- 丁：对账目录（偏了挡，清理后再对体积） ----------

def test_reconcile_blocked_while_skewed_and_passes_after_purge(db):
    plan = plans.list_plans(db_path=db)[0]
    plans.publish_plan(plan["id"], db_path=db)
    f = _first_attached(db)
    files.void_file(f["id"], db_path=db)

    with pytest.raises(ServiceError) as ei:
        reconcile.run_reconcile(plan["id"], db_path=db)
    assert ei.value.status_code == 409

    purge_ghosts(db_path=db)
    job = rewrite.start_rewrite(plan["id"], db_path=db)
    report = reconcile.run_reconcile(plan["id"], db_path=db)
    # 午：清理后再核对体积才收
    assert report["before_bytes"] == report["after_bytes"] == job["merged_bytes"]
    assert report["file_count"] == 2  # 3 个挂载里剔掉 1 个幽灵


# ---------- 己：服务端一次写完 + 锁（双仓管并发） ----------

def test_purge_is_one_shot_atomic_and_concurrency_safe(db):
    plan = plans.list_plans(db_path=db)[0]
    targets = [
        x for x in files.list_files(db_path=db) if x["status"] == "已入计划"
    ][:2]
    for t in targets:
        files.void_file(t["id"], db_path=db)
    assert ghost_count(None, db) == 2

    results: list[dict] = []
    errors: list[Exception] = []

    def worker():
        try:
            results.append(purge_ghosts(db_path=db))
        except Exception as exc:  # pragma: no cover - 锁失败也要可见
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    # 缺锁场景的双成功互相覆盖不会发生：删除总数恰好等于幽灵数
    assert sum(r["removed"] for r in results) == 2
    assert sorted(r["remaining_ghosts"] for r in results) == [0, 0]
    assert ghost_count(None, db) == 0
    assert ghost_mounts(db) == []

    # 凭证全部回填撤销时间与备注
    for v in list_vouchers(db):
        assert v["revoked_at"]
        assert v["revoke_note"]

    # 亥：失败回滚保护——制造失败时挂载行与凭证都不动
    targets2 = [x for x in files.list_files(db_path=db) if x["status"] == "碎文件"]
    if targets2:
        files.void_file(targets2[0]["id"], db_path=db)
        before_rows = _raw_ghost_rows(db)
        with pytest.raises(Exception):
            _failing_purge(db)
        assert _raw_ghost_rows(db) == before_rows


def _raw_ghost_rows(db):
    with get_db(db) as conn:
        return [
            tuple(r)
            for r in conn.execute(
                "SELECT plan_id, file_id FROM plan_items i "
                "JOIN lake_files f ON f.id=i.file_id WHERE f.status='作废' "
                "ORDER BY plan_id, file_id"
            ).fetchall()
        ]


def _failing_purge(db):
    """模拟清理中途失败：必须整体回滚，不留半态。"""
    from app.db import get_db as _get_db

    with _get_db(db) as conn:
        conn.isolation_level = None
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "DELETE FROM plan_items WHERE file_id IN "
            "(SELECT id FROM lake_files WHERE status='作废')"
        )
        raise RuntimeError("boom after delete, before voucher update")


# ---------- 酉：页面芯片与库表双查（无假绿、无半修） ----------

def test_surface_always_aligned_with_database(db):
    snap = snapshot(db)
    assert snap["aligned"] is True
    assert snap["panel_chip"] == snap["truth"] == "已剔幽灵"

    f = _first_attached(db)
    files.void_file(f["id"], db_path=db)
    snap = snapshot(db)
    # 双轨幽灵勿并开：有残留时芯片不能再亮“已剔幽灵”
    assert snap["panel_chip"] == snap["truth"] == "项残留"
    assert snap["ghost_count"] == 1

    dash = dashboard(db)
    assert dash["fake_green"] is False
    assert dash["chip"] == "项残留"
    assert len(dash["vouchers"]) == 1
    assert len(dash["mounts"]) == 1

    purge_ghosts(db_path=db)
    dash = dashboard(db)
    assert dash["chip"] == dash["truth"] == "已剔幽灵"
    assert dash["fake_green"] is False
    assert dash["ghost_count"] == 0
    # 账册/物化行可查
    assert all(v["revoked_at"] for v in dash["vouchers"])


def test_no_display_only_half_fix_surface_exists():
    # 半修入口必须已拆除，只剩真清理
    import app.services.void_ledger as vl
    import app.services.void_ghost_surface as vs

    assert not hasattr(vl, "scrub_display_only")
    assert not hasattr(vs, "reconcile_surface")
    assert not hasattr(vs, "paint_ok")
    assert not hasattr(vs, "seed_skew")


def test_purge_specific_file_only_touches_that_ghost(db):
    plan = plans.list_plans(db_path=db)[0]
    attached = [x for x in files.list_files(db_path=db) if x["status"] == "已入计划"]
    files.void_file(attached[0]["id"], db_path=db)
    files.void_file(attached[1]["id"], db_path=db)
    assert ghost_count(plan["id"], db) == 2

    result = purge_ghosts(file_id=attached[0]["id"], db_path=db)
    assert result["removed"] == 1
    assert result["remaining_ghosts"] == 1
    remaining = ghost_items(plan["id"], db)
    assert [g["id"] for g in remaining] == [attached[1]["id"]]
