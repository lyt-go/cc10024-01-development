"""转换规则领域服务：字段映射与转换函数，受clean_pipeline调度，向field_normalize和quality_guard输出。"""
from __future__ import annotations

from typing import Any

from app.store import store
from app.services.base import BaseModuleService, register_hook
from app import persistence as persist


class TransformRuleService(BaseModuleService):
    MODULE = "transform_rule"
    ENTITY = "转换规则"
    OPERATION_TERM = "转换"
    LIST_FIELDS = ["规则编号", "关联工序", "源字段", "目标字段", "转换函数", "依赖字段", "空值处理", "规则版本"]
    REQUIRED_FIELDS = ["规则编号", "关联工序", "源字段"]
    STATUS_ORDER = ["草稿", "待校验", "已生效", "已废弃"]
    ACTION_RULES = {"提交校验": "待校验", "标记生效": "已生效", "标记废弃": "已废弃"}
    NEGATIVE_ACTIONS = []

    def domain_snapshot(self) -> dict[str, Any]:
        base = super().domain_snapshot()
        rules = store.rows(self.MODULE)
        pipelines = store.rows("clean_pipeline")
        pipeline_ids = {r.get("工序编号") for r in pipelines}
        base["orphan_rules"] = sum(1 for r in rules if r.get("关联工序") not in pipeline_ids)
        # 归一化消费
        norms = store.rows("field_normalize")
        base["downstream_norms"] = len(norms)
        return base