"""财务报表管理路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.fin_report import ReportCreate, ReportUpdate
from app.services.fin_report import ReportService

router = APIRouter(prefix="/api/finance/reports", tags=["finance-reports"])


@router.get("")
async def list_reports(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    report_type: str | None = Query(default=None),
    period: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ReportService.list_reports(
        session, limit=limit, offset=offset, report_type=report_type, period=period
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_report(
    payload: ReportCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ReportService.create_report(session, payload, request)


@router.get("/{report_id}")
async def get_report(
    report_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ReportService.get_report(session, report_id)


@router.patch("/{report_id}")
async def update_report(
    report_id: str, payload: ReportUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ReportService.update_report(session, report_id, payload, request)


@router.post("/{report_id}/finalize")
async def finalize_report(
    report_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ReportService.finalize_report(session, report_id, request)


@router.delete("/{report_id}")
async def delete_report(
    report_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ReportService.delete_report(session, report_id, request)
