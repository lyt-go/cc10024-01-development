"""画布配置领域服务：浏览器画布参数配置，消费login_mgr站点信息，为page_snapshot提供渲染参数。"""
from __future__ import annotations

from typing import Any

from app.store import store
from app.services.base import BaseModuleService
from app import persistence as persist


class CanvasConfigService(BaseModuleService):
    MODULE = "canvas_config"
    ENTITY = "画布配置"
    OPERATION_TERM = "关联"
    LIST_FIELDS = ["配置编号", "关联站点", "分辨率", "像素比", "字符集", "禁用资源", "滚动模式", "拦截清单"]
    REQUIRED_FIELDS = ["配置编号", "关联站点", "分辨率"]
    STATUS_ORDER = ["草稿", "待校验", "已生效", "已停用"]
    ACTION_RULES = {"提交校验": "待校验", "标记生效": "已生效", "停用配置": "已停用"}
    NEGATIVE_ACTIONS = ["停用配置"]

    def domain_snapshot(self) -> dict[str, Any]:
        base = super().domain_snapshot()
        # 关联的登录凭证
        credentials = store.rows("login_mgr")
        canvases = store.rows(self.MODULE)
        canvas_sites = {r.get("关联站点") for r in canvases}
        base["sites_with_credentials"] = sum(
            1 for c in credentials if c.get("目标站点") in canvas_sites and c.get("status") == "有效")
        # 关联的page_snapshot
        snapshots = store.rows("page_snapshot")
        base["linked_snapshots"] = sum(
            1 for s in snapshots if s.get("采集来源") in canvas_sites)
        return base