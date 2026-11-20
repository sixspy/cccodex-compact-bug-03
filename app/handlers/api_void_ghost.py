from app.handlers.base import BaseHandler
from app.services.void_ghost_ledger import append_ledger, dashboard
from app.services.void_ghost_surface import reconcile_surface, snapshot


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


class ApiVoidGhostHalf(BaseHandler):
    def post(self):
        self.require_user()
        self.json(reconcile_surface())


class ApiVoidGhostSnap(BaseHandler):
    def get(self):
        self.require_user()
        self.json(snapshot())
