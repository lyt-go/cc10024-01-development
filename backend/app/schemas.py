"""通用接口契约；模块字段由领域服务持有，不再为每个模块复制一份模型类。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None


class ActionPayload(BaseModel):
    action: str
    remark: str | None = None


class RehearsalPagePayload(BaseModel):
    """录入页面版本：DOM 快照全文 + 版本号。"""

    模板编号: str
    页面版本: str
    dom: str
    采集来源: str | None = None


class RehearsalRunPayload(BaseModel):
    页面版本: str


class RehearsalConfirmPayload(BaseModel):
    """提交预演：采纳某个锚点作为该字段唯一可执行来源。"""

    页面版本: str
    锚点编号: str
