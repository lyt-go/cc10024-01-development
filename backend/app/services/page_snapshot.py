"""页面快照领域服务：页面DOM快照的采集与存储，消费login_mgr凭证和canvas_config配置。"""
from __future__ import annotations

from typing import Any

from app.store import store
from app.services.base import BaseModuleService, register_hook
from app import persistence as persist


class PageSnapshotService(BaseModuleService):
    MODULE = "page_snapshot"
    ENTITY = "页面快照"
    OPERATION_TERM = "采集"
    LIST_FIELDS = ["快照编号", "采集来源", "页面版本", "DOM摘要", "快照时间", "快照类型", "数据量", "回收时间"]
    REQUIRED_FIELDS = ["快照编号", "采集来源", "页面版本"]
    STATUS_ORDER = ["草稿", "已存档", "已清洗", "已回收"]
    ACTION_RULES = {"标记存档": "已存档", "确认清洗": "已清洗", "启动回收": "已回收"}
    NEGATIVE_ACTIONS = []

    def capture_snapshot(self, page_url: str, dom_hash: str, raw_dom: str) -> dict[str, Any]:
        """采集页面快照并存入snapshots/目录。"""
        snapshot = {
            "page_url": page_url,
            "dom_hash": dom_hash,
            "raw_dom_length": len(raw_dom),
            "timestamp": persist.now_iso(),
            "dom_preview": raw_dom[:500],
        }
        persist.write_json("snapshots", f"page_{dom_hash}.json", snapshot)
        return snapshot

    def domain_snapshot(self) -> dict[str, Any]:
        base = super().domain_snapshot()
        snap_files = persist.list_files("snapshots", ".json")
        base["snapshot_files"] = len([f for f in snap_files if f.startswith("page_")])
        # 关联的登录凭证
        credentials = store.rows("login_mgr")
        snaps = store.rows(self.MODULE)
        sites = {r.get("采集来源") for r in snaps}
        base["sites_with_credentials"] = sum(1 for c in credentials if c.get("目标站点") in sites)
        return base