"""质量防护领域服务：数据质量校验、异常检测、阻断策略，消费clean_pipeline和transform_rule输出。"""
from __future__ import annotations

from typing import Any

from app.store import store
from app.services.base import BaseModuleService, register_hook
from app import persistence as persist


class QualityGuardService(BaseModuleService):
    MODULE = "quality_guard"
    ENTITY = "质量规则"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["规则编号", "检核对象", "检核维度", "合规阈值", "阻断策略", "实例范围", "采样率", "规则版本"]
    REQUIRED_FIELDS = ["规则编号", "检核对象", "检核维度"]
    STATUS_ORDER = ["草稿", "待校验", "已生效", "已停用"]
    ACTION_RULES = {"提交校验": "待校验", "标记生效": "已生效", "停用规则": "已停用"}
    NEGATIVE_ACTIONS = ["停用规则"]

    def run_quality_report(self, target_module: str) -> dict[str, Any]:
        """对指定目标模块执行质量检查，产出报告并持久化到reports/。"""
        rows = store.rows(target_module)
        rules = [r for r in store.rows(self.MODULE) if r.get("检核对象") == target_module]
        total = len(rows)
        abnormal = sum(1 for r in rows if r.get("abnormal"))
        compliance = 1.0 if total == 0 else (total - abnormal) / total
        report = {
            "target": target_module,
            "total_records": total,
            "abnormal_records": abnormal,
            "compliance_rate": compliance,
            "applied_rules": len(rules),
            "timestamp": persist.now_iso(),
        }
        persist.append_jsonl("reports", "quality_report.jsonl", report)
        return report

    def domain_snapshot(self) -> dict[str, Any]:
        base = super().domain_snapshot()
        # 质量报告汇总
        reports = persist.read_jsonl("reports", "quality_report.jsonl")
        if reports:
            latest = reports[-1]
            base["latest_compliance"] = latest.get("compliance_rate")
            base["total_reports"] = len(reports)
        # 关联的schema校验
        schemas = store.rows("schema_check")
        base["linked_schema_rules"] = len(schemas)
        return base