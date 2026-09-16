"""财务凭证服务层：借贷平衡校验与过账状态机。"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.fin_voucher import FinVoucher
from app.models.fin_voucher_entry import FinVoucherEntry
from app.repositories import fin_account as account_repo
from app.repositories import fin_voucher as repo
from app.schemas.fin_voucher import VoucherCreate, VoucherUpdate
from app.services.audit import record_audit


def _entry_to_dict(e: FinVoucherEntry) -> dict:
    return {
        "id": e.id, "account_id": e.account_id, "direction": e.direction,
        "amount": e.amount, "summary": e.summary,
    }


def _voucher_to_dict(v: FinVoucher, entries: list[FinVoucherEntry] | None = None) -> dict:
    result = {
        "id": v.id, "voucher_no": v.voucher_no, "voucher_date": v.voucher_date,
        "summary": v.summary, "status": v.status,
        "total_debit": v.total_debit, "total_credit": v.total_credit,
        "posted_at": v.posted_at, "remark": v.remark,
        "created_at": v.created_at.isoformat() if v.created_at else "",
        "updated_at": v.updated_at.isoformat() if v.updated_at else "",
    }
    if entries is not None:
        result["entries"] = [_entry_to_dict(e) for e in entries]
    return result


class VoucherService:
    @staticmethod
    async def list_vouchers(session: AsyncSession, limit: int, offset: int,
                            status_filter: str | None, voucher_date: str | None) -> dict:
        rows = await repo.list_vouchers(session, limit=limit, offset=offset,
                                        status=status_filter, voucher_date=voucher_date)
        total = await repo.count_vouchers(session, status=status_filter, voucher_date=voucher_date)
        return {"total": total, "items": [_voucher_to_dict(v) for v in rows]}

    @staticmethod
    async def get_voucher(session: AsyncSession, voucher_id: str) -> dict:
        v = await repo.get_voucher(session, voucher_id)
        if not v:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "凭证不存在")
        entries = await repo.list_entries(session, voucher_id)
        return _voucher_to_dict(v, entries)

    @staticmethod
    async def create_voucher(session: AsyncSession, payload: VoucherCreate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if await repo.get_voucher_by_no(session, payload.voucher_no):
            raise HTTPException(status.HTTP_409_CONFLICT, "凭证号已存在")
        # 借贷平衡校验
        total_debit = sum(e.amount for e in payload.entries if e.direction == "debit")
        total_credit = sum(e.amount for e in payload.entries if e.direction == "credit")
        if total_debit <= 0 or abs(total_debit - total_credit) > 1e-9:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "借贷不平衡：借方合计必须等于贷方合计且大于 0")
        # 科目存在性校验
        for e in payload.entries:
            if not await account_repo.get_account(session, e.account_id):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"明细科目不存在: {e.account_id}")
        voucher = FinVoucher(
            id=str(uuid.uuid4()), voucher_no=payload.voucher_no,
            voucher_date=payload.voucher_date, summary=payload.summary,
            status="draft", total_debit=total_debit, total_credit=total_credit,
            remark=payload.remark,
        )
        voucher = await repo.create_voucher(session, voucher)
        entries = [
            FinVoucherEntry(
                id=str(uuid.uuid4()), voucher_id=voucher.id, account_id=e.account_id,
                direction=e.direction, amount=e.amount, summary=e.summary,
            )
            for e in payload.entries
        ]
        await repo.add_entries(session, entries)
        await record_audit(session, "finance.voucher.created", "internal",
                           f"voucher_no={payload.voucher_no}", request)
        return _voucher_to_dict(voucher, entries)

    @staticmethod
    async def update_voucher(session: AsyncSession, voucher_id: str,
                             payload: VoucherUpdate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        v = await repo.get_voucher(session, voucher_id)
        if not v:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "凭证不存在")
        if v.status == "posted":
            raise HTTPException(status.HTTP_409_CONFLICT, "已过账凭证不可修改")
        for field in ("voucher_date", "summary", "remark"):
            value = getattr(payload, field)
            if value is not None:
                setattr(v, field, value)
        v = await repo.update_voucher(session, v)
        await record_audit(session, "finance.voucher.updated", "internal",
                           f"voucher_id={voucher_id}", request)
        entries = await repo.list_entries(session, voucher_id)
        return _voucher_to_dict(v, entries)

    @staticmethod
    async def post_voucher(session: AsyncSession, voucher_id: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        v = await repo.get_voucher(session, voucher_id)
        if not v:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "凭证不存在")
        if v.status == "posted":
            raise HTTPException(status.HTTP_409_CONFLICT, "凭证已过账，不可重复过账")
        v.status = "posted"
        from datetime import UTC, datetime
        v.posted_at = datetime.now(UTC).isoformat()
        v = await repo.update_voucher(session, v)
        await record_audit(session, "finance.voucher.posted", "internal",
                           f"voucher_id={voucher_id}", request)
        entries = await repo.list_entries(session, voucher_id)
        return _voucher_to_dict(v, entries)

    @staticmethod
    async def delete_voucher(session: AsyncSession, voucher_id: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        v = await repo.get_voucher(session, voucher_id)
        if not v:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "凭证不存在")
        if v.status == "posted":
            raise HTTPException(status.HTTP_409_CONFLICT, "已过账凭证不可删除")
        await repo.delete_entries(session, voucher_id)
        await repo.delete_voucher(session, v)
        await record_audit(session, "finance.voucher.deleted", "internal",
                           f"voucher_id={voucher_id}", request)
        return {"deleted": True, "id": voucher_id}
