from app.handlers.base import BaseHandler
from app.services.void_ghost_ledger import append_ledger, dashboard
from app.services.void_ledger import purge_ghosts
from app.services.void_ghost_surface import snapshot


class ApiVoidGhostDash(BaseHandler):
    def get(self):
        self.require_user()
        self.json(dashboard())


class ApiVoidGhostNote(BaseHandler):
    def post(self):
        self.require_user()
        body = self.read_json()
        self.json(
            append_ledger(
                int(body.get("plan_id") or 0),
                str(body.get("note") or "作废幽灵"),
            )
        )


class ApiVoidGhostPurge(BaseHandler):
    """仓管清理幽灵：服务端一次写完（凭证+删挂载行，同事务同写锁）。"""

    def post(self):
        self.require_user()
        body = self.read_json()
        raw = body.get("file_id")
        file_id = int(raw) if raw not in (None, "") else None
        result = purge_ghosts(file_id)
        append_ledger(
            0,
            f"清理幽灵 {result['removed']} 项，剩余 {result['remaining_ghosts']}",
        )
        self.json({"purge": result, "snapshot": snapshot()})


class ApiVoidGhostSnap(BaseHandler):
    def get(self):
        self.require_user()
        self.json(snapshot())
