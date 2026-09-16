"""财务凭证 Pydantic 模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class VoucherEntryIn(BaseModel):
    """凭证明细行入参。"""
    account_id: str = Field(min_length=1, max_length=64)
    direction: Literal["debit", "credit"]
    amount: float = Field(gt=0)
    summary: str = Field(default="", max_length=512)


class VoucherCreate(BaseModel):
    voucher_no: str = Field(min_length=2, max_length=64, pattern=r"^[0-9A-Za-z_-]+$")
    voucher_date: str = Field(min_length=8, max_length=32)
    summary: str = Field(default="", max_length=512)
    entries: list[VoucherEntryIn] = Field(min_length=2)
    remark: str = Field(default="", max_length=2000)


class VoucherUpdate(BaseModel):
    voucher_date: str | None = Field(default=None, max_length=32)
    summary: str | None = Field(default=None, max_length=512)
    remark: str | None = Field(default=None, max_length=2000)
