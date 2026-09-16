"""财务科目服务层。"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.fin_account import FinAccount
from app.repositories import fin_account as repo
from app.schemas.fin_account import AccountCreate, AccountUpdate
from app.services.audit import record_audit


def _to_dict(a: FinAccount) -> dict:
    return {
        "id": a.id, "code": a.code, "name": a.name, "category": a.category,
        "opening_balance": a.opening_balance, "status": a.status, "remark": a.remark,
        "created_at": a.created_at.isoformat() if a.created_at else "",
        "updated_at": a.updated_at.isoformat() if a.updated_at else "",
    }


class AccountService:
    @staticmethod
    async def list_accounts(session: AsyncSession, limit: int, offset: int,
                            category: str | None, keyword: str | None) -> dict:
        rows = await repo.list_accounts(session, limit=limit, offset=offset,
                                        category=category, keyword=keyword)
        total = await repo.count_accounts(session, category=category, keyword=keyword)
        return {"total": total, "items": [_to_dict(a) for a in rows]}

    @staticmethod
    async def get_account(session: AsyncSession, account_id: str) -> dict:
        a = await repo.get_account(session, account_id)
        if not a:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "会计科目不存在")
        return _to_dict(a)

    @staticmethod
    async def create_account(session: AsyncSession, payload: AccountCreate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if await repo.get_account_by_code(session, payload.code):
            raise HTTPException(status.HTTP_409_CONFLICT, "科目编码已存在")
        account = FinAccount(
            id=str(uuid.uuid4()), code=payload.code, name=payload.name,
            category=payload.category, opening_balance=payload.opening_balance,
            remark=payload.remark, status="active",
        )
        account = await repo.create_account(session, account)
        await record_audit(session, "finance.account.created", "internal",
                           f"code={payload.code}", request)
        return _to_dict(account)

    @staticmethod
    async def update_account(session: AsyncSession, account_id: str,
                             payload: AccountUpdate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        a = await repo.get_account(session, account_id)
        if not a:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "会计科目不存在")
        for field in ("name", "opening_balance", "remark"):
            value = getattr(payload, field)
            if value is not None:
                setattr(a, field, value)
        a = await repo.update_account(session, a)
        await record_audit(session, "finance.account.updated", "internal",
                           f"account_id={account_id}", request)
        return _to_dict(a)

    @staticmethod
    async def update_status(session: AsyncSession, account_id: str,
                            new_status: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        a = await repo.get_account(session, account_id)
        if not a:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "会计科目不存在")
        a.status = new_status
        a = await repo.update_account(session, a)
        await record_audit(session, "finance.account.status_changed", "internal",
                           f"account_id={account_id} status={new_status}", request)
        return _to_dict(a)

    @staticmethod
    async def delete_account(session: AsyncSession, account_id: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        a = await repo.get_account(session, account_id)
        if not a:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "会计科目不存在")
        await repo.delete_account(session, a)
        await record_audit(session, "finance.account.deleted", "internal",
                           f"account_id={account_id}", request)
        return {"deleted": True, "id": account_id}
