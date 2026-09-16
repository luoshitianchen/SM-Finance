"""财务科目 Pydantic 模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AccountCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[0-9A-Za-z_-]+$")
    name: str = Field(min_length=1, max_length=256)
    category: Literal["asset", "liability", "equity", "income", "expense"]
    opening_balance: float = Field(default=0.0, ge=0)
    remark: str = Field(default="", max_length=2000)


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=256)
    opening_balance: float | None = Field(default=None, ge=0)
    remark: str | None = Field(default=None, max_length=2000)


class AccountStatusUpdate(BaseModel):
    status: Literal["active", "closed"]
