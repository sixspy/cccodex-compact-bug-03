# 湖表压实台（cc-compact-lab）

CC_Codex 二期数据工程产品线：Tornado + 原生 JS 时间轴 SPA + SQLite。

## 主链

1. 小文件清单：登记湖区碎文件与体积
2. 压实计划：把碎文件编入计划
3. 重写合并：执行合并任务并回写状态
4. 体积对账：计划前后体积对照报告
5. 台参数：现行压实阈值与阈值说明

默认账号 `admin` / `123456`，端口 `7300`。

## 作废幽灵彻清（compact-bug-03）

碎文件作废后会留作计划幽灵挂载，采用彻清路线（唯一真相源）：

1. 作废即写 `void_vouchers` 作废凭证，挂载行暂留为幽灵；
2. 清理（`POST /api/void_ghost/purge`）在同一事务、`BEGIN IMMEDIATE` 写锁内
   一次写完：回填凭证撤销信息 → 删除 `plan_items` 挂载行，失败整体回滚；
3. 双仓管并发清理由写锁串行化，后到者幂等空转，不会双成功互相覆盖；
4. 芯片（已剔幽灵 / 项残留）只由库内真实残留推导，无独立展示双源、无假绿、无半修；
5. 计划总字节、对账 `before_bytes` 立刻剔除幽灵；幽灵未清理时合并与对账一律 409 挡回，
   幽灵项不会再进入合并可选项；清理后再核对体积才收口。

## 本地

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
python run.py
```
