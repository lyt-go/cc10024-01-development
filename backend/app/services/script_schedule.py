"""脚本调度领域服务：消费behavior_script脚本，创建调度计划、驱动batch_queue执行。"""
from __future__ import annotations

from typing import Any

from app.store import store
from app.services.base import BaseModuleService, register_hook
from app import persistence as persist


def _create_batch_on_start(entry: dict[str, Any]) -> None:
    """调度计划启动运行时，自动创建batch_queue批次。"""
    batch_rows = store.rows("batch_queue")
    new_id = max((int(r.get("id", 0)) for r in batch_rows), default=0) + 1
    batch = {
        "id": new_id,
        "批次编号": f"BATC-AUTO-{new_id:04d}",
        "关联计划": entry.get("计划编号", ""),
        "任务数量": 10,
        "完成数": "0",
        "失败数": "0",
        "批次状态": "由调度自动生成",
        "截止时间": persist.now_iso(),
        "优先级": "中",
        "status": "排队中",
        "pending": True,
        "abnormal": False,
        "version": "",
        "updated_at": persist.now_iso(),
    }
    batch_rows.append(batch)
    persist.append_jsonl("runs", "batch_queue.jsonl", {
        "module": "batch_queue", "entity": "采集批次", "entry_id": new_id,
        "status": "排队中", "version": "", "action": "auto_create_from_schedule",
        "timestamp": persist.now_iso(), "abnormal": False,
        "source_module": "script_schedule", "source_id": entry.get("id"),
    })

register_hook("script_schedule", "启动运行", _create_batch_on_start)


class ScriptScheduleService(BaseModuleService):
    MODULE = "script_schedule"
    ENTITY = "调度计划"
    OPERATION_TERM = "调度"
    LIST_FIELDS = ["计划编号", "关联脚本", "触发条件", "执行间隔", "重跑策略", "依赖任务", "超时控制", "计划状态"]
    REQUIRED_FIELDS = ["计划编号", "关联脚本", "触发条件"]
    STATUS_ORDER = ["草稿", "待校验", "运行中", "已暂停"]
    ACTION_RULES = {"提交校验": "待校验", "启动运行": "运行中", "暂停调度": "已暂停"}
    NEGATIVE_ACTIONS = []

    def domain_snapshot(self) -> dict[str, Any]:
        base = super().domain_snapshot()
        # 关联的batch_queue统计
        batches = store.rows("batch_queue")
        schedules = store.rows(self.MODULE)
        plan_ids = {r.get("计划编号") for r in schedules}
        base["downstream_batches"] = sum(1 for b in batches if b.get("关联计划") in plan_ids)
        # 关联的error_recover任务
        errors = store.rows("error_recover")
        base["recovery_tasks"] = sum(1 for e in errors if e.get("关联计划") in plan_ids)
        return base