"""页面去重领域服务：页面内容相似度检测与去重，消费page_snapshot快照数据，为export_channel提供去重结果。"""
from __future__ import annotations

import hashlib
from typing import Any

from app.store import store
from app.services.base import BaseModuleService
from app import persistence as persist


class PageDedupService(BaseModuleService):
    MODULE = "page_dedup"
    ENTITY = "去重规则"
    OPERATION_TERM = "去重"
    LIST_FIELDS = ["规则编号", "去重维度", "特征字段", "相似算法", "指纹长度", "时间窗口", "冲突策略", "规则版本"]
    REQUIRED_FIELDS = ["规则编号", "去重维度", "特征字段"]
    STATUS_ORDER = ["草稿", "待校验", "已生效", "已停用"]
    ACTION_RULES = {"提交校验": "待校验", "标记生效": "已生效", "停用规则": "已停用"}
    NEGATIVE_ACTIONS = ["停用规则"]

    def compute_fingerprint(self, content: str, rule_id: int) -> str:
        """根据去重规则计算内容的指纹。"""
        rule = store.find(self.MODULE, rule_id)
        algorithm = rule.get("相似算法", "md5") if rule else "md5"
        if algorithm == "sha256":
            return hashlib.sha256(content.encode()).hexdigest()[:32]
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def deduplicate_pages(self, pages: list[dict[str, Any]], rule_id: int) -> dict[str, Any]:
        """对页面列表执行去重，返回去重结果和统计。"""
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        duplicates: list[dict[str, Any]] = []
        for page in pages:
            fp = self.compute_fingerprint(str(page), rule_id)
            if fp in seen:
                duplicates.append({**page, "fingerprint": fp})
            else:
                seen.add(fp)
                unique.append({**page, "fingerprint": fp})
        result = {
            "rule_id": rule_id,
            "total": len(pages),
            "unique": len(unique),
            "duplicates": len(duplicates),
            "timestamp": persist.now_iso(),
        }
        persist.append_jsonl("reports", "dedup_report.jsonl", result)
        return result

    def domain_snapshot(self) -> dict[str, Any]:
        base = super().domain_snapshot()
        # 去重报告消费
        reports = persist.read_jsonl("reports", "dedup_report.jsonl")
        base["dedup_reports"] = len(reports)
        # 关联的导出配置
        channels = store.rows("export_channel")
        base["export_channels"] = len(channels)
        return base