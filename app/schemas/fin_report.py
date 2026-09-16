"""财务报表 Pydantic 模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    period: str = Field(min_length=6, max_length=16)
    type: Literal["balance_sheet", "income_statement", "cash_flow"]
    title: str = Field(default="", max_length=256)
    data: str = Field(default="{}", max_length=100000)
    remark: str = Field(default="", max_length=2000)


class ReportUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    data: str | None = Field(default=None, max_length=100000)
    remark: str | None = Field(default=None, max_length=2000)


class ReportStatusUpdate(BaseModel):
    status: Literal["draft", "finalized"]
