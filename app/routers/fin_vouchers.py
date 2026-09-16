"""财务凭证管理路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.fin_voucher import VoucherCreate, VoucherUpdate
from app.services.fin_voucher import VoucherService

router = APIRouter(prefix="/api/finance/vouchers", tags=["finance-vouchers"])


@router.get("")
async def list_vouchers(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    voucher_date: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await VoucherService.list_vouchers(
        session, limit=limit, offset=offset,
        status_filter=status_filter, voucher_date=voucher_date
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_voucher(
    payload: VoucherCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await VoucherService.create_voucher(session, payload, request)


@router.get("/{voucher_id}")
async def get_voucher(
    voucher_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await VoucherService.get_voucher(session, voucher_id)


@router.patch("/{voucher_id}")
async def update_voucher(
    voucher_id: str, payload: VoucherUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await VoucherService.update_voucher(session, voucher_id, payload, request)


@router.post("/{voucher_id}/post")
async def post_voucher(
    voucher_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await VoucherService.post_voucher(session, voucher_id, request)


@router.delete("/{voucher_id}")
async def delete_voucher(
    voucher_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await VoucherService.delete_voucher(session, voucher_id, request)
