"""登录凭证领域服务：站点认证凭证管理，驱动canvas_config和page_snapshot。"""
from __future__ import annotations

from typing import Any

from app.store import store
from app.services.base import BaseModuleService, register_hook
from app import persistence as persist


class LoginMgrService(BaseModuleService):
    MODULE = "login_mgr"
    ENTITY = "登录凭证"
    OPERATION_TERM = "采集"
    LIST_FIELDS = ["凭证编号", "目标站点", "认证方式", "Token摘要", "凭证状态", "过期时间", "失效策略", "刷新频率"]
    REQUIRED_FIELDS = ["凭证编号", "目标站点", "认证方式"]
    STATUS_ORDER = ["草稿", "待校验", "有效", "已失效"]
    ACTION_RULES = {"提交校验": "待校验", "标记有效": "有效", "标记失效": "已失效"}
    NEGATIVE_ACTIONS = []

    def domain_snapshot(self) -> dict[str, Any]:
        base = super().domain_snapshot()
        credentials = store.rows(self.MODULE)
        base["active_credentials"] = sum(1 for c in credentials if c.get("status") == "有效")
        # 关联的canvas_config
        canvases = store.rows("canvas_config")
        sites = {r.get("目标站点") for r in credentials}
        base["linked_canvases"] = sum(1 for c in canvases if c.get("关联站点") in sites)
        # 关联的page_snapshot
        snapshots = store.rows("page_snapshot")
        base["linked_snapshots"] = sum(1 for s in snapshots if s.get("采集来源") in sites)
        return base