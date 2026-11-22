"""抽取锚点绑定预演接口：页面版本录入、预演运行、来源确认与预演视图。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import (
    ActionResult,
    RehearsalConfirmPayload,
    RehearsalPagePayload,
    RehearsalRunPayload,
)
from app.seed import REHEARSAL_V2_DOM
from app.services.extract_rehearsal import ExtractRehearsalService, RehearsalError

router = APIRouter(prefix="/api/rehearsal", tags=["抽取锚点预演"])

_service = ExtractRehearsalService()


@router.get("/sample-dom")
def sample_dom() -> dict[str, str]:
    """演示用的第二版页面 DOM：结构不同，供“录入第二版页面”一键填充。"""
    return {"页面版本": "product-v2", "dom": REHEARSAL_V2_DOM}


@router.get("/{template_code}")
def rehearsal_view(template_code: str) -> dict:
    """预演视图：每版实际获得的值、字段定位清单、样本行与冲突排除项。"""
    try:
        return _service.rehearsal_view(template_code)
    except RehearsalError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/pages", response_model=ActionResult)
def register_page(payload: RehearsalPagePayload) -> ActionResult:
    """录入页面版本（DOM 快照），同步在页面快照模块登记。"""
    try:
        page = _service.register_page(
            payload.模板编号, payload.页面版本, payload.dom, payload.采集来源,
        )
    except RehearsalError as exc:
        return ActionResult(ok=False, message=str(exc))
    return ActionResult(ok=True, message=f"页面版本 {payload.页面版本} 已录入", entry=page)


@router.post("/{template_code}/run", response_model=ActionResult)
def run_rehearsal(template_code: str, payload: RehearsalRunPayload) -> ActionResult:
    """运行预演：评估候选锚点，把实际匹配写入字段定位清单。"""
    try:
        result = _service.run_rehearsal(template_code, payload.页面版本)
    except RehearsalError as exc:
        return ActionResult(ok=False, message=str(exc))
    hits = sum(1 for e in result["evaluations"] if e["命中"])
    conflict_note = "，存在锚点冲突" if result["conflict"] else ""
    return ActionResult(
        ok=True,
        message=f"预演完成：{hits} 个锚点命中{conflict_note}，匹配已写入字段定位清单",
        entry=result,
    )


@router.post("/{template_code}/confirm", response_model=ActionResult)
def confirm_binding(template_code: str, payload: RehearsalConfirmPayload) -> ActionResult:
    """提交预演：确立该字段唯一可执行来源，其余匹配转为冲突未采纳。"""
    try:
        manifest = _service.confirm_binding(template_code, payload.页面版本, payload.锚点编号)
    except RehearsalError as exc:
        return ActionResult(ok=False, message=str(exc))
    confirmed = manifest["confirmed"]
    return ActionResult(
        ok=True,
        message=(
            f"已确立可执行来源：{confirmed['锚点编号']}"
            f"（采纳值 {confirmed['值']}，来源版本 {confirmed['页面版本']}）"
        ),
        entry=manifest,
    )
