"""财务科目管理路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.fin_account import AccountCreate, AccountStatusUpdate, AccountUpdate
from app.services.fin_account import AccountService

router = APIRouter(prefix="/api/finance/accounts", tags=["finance-accounts"])


@router.get("")
async def list_accounts(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    category: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await AccountService.list_accounts(
        session, limit=limit, offset=offset, category=category, keyword=keyword
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AccountCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await AccountService.create_account(session, payload, request)


@router.get("/{account_id}")
async def get_account(
    account_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await AccountService.get_account(session, account_id)


@router.patch("/{account_id}")
async def update_account(
    account_id: str, payload: AccountUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await AccountService.update_account(session, account_id, payload, request)


@router.patch("/{account_id}/status")
async def update_account_status(
    account_id: str, payload: AccountStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await AccountService.update_status(session, account_id, payload.status, request)


@router.delete("/{account_id}")
async def delete_account(
    account_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await AccountService.delete_account(session, account_id, request)
