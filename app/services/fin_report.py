"""财务报表服务层：期间报表快照管理。"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.fin_report import FinReport
from app.repositories import fin_report as repo
from app.schemas.fin_report import ReportCreate, ReportUpdate
from app.services.audit import record_audit


def _to_dict(r: FinReport) -> dict:
    return {
        "id": r.id, "period": r.period, "type": r.type, "title": r.title,
        "data": r.data, "status": r.status, "remark": r.remark,
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "updated_at": r.updated_at.isoformat() if r.updated_at else "",
    }


class ReportService:
    @staticmethod
    async def list_reports(session: AsyncSession, limit: int, offset: int,
                           report_type: str | None, period: str | None) -> dict:
        rows = await repo.list_reports(session, limit=limit, offset=offset,
                                       report_type=report_type, period=period)
        total = await repo.count_reports(session, report_type=report_type, period=period)
        return {"total": total, "items": [_to_dict(r) for r in rows]}

    @staticmethod
    async def get_report(session: AsyncSession, report_id: str) -> dict:
        r = await repo.get_report(session, report_id)
        if not r:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "报表不存在")
        return _to_dict(r)

    @staticmethod
    async def create_report(session: AsyncSession, payload: ReportCreate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if await repo.get_report_by_period_type(session, payload.period, payload.type):
            raise HTTPException(status.HTTP_409_CONFLICT, "该期间报表已存在")
        report = FinReport(
            id=str(uuid.uuid4()), period=payload.period, type=payload.type,
            title=payload.title, data=payload.data, remark=payload.remark, status="draft",
        )
        report = await repo.create_report(session, report)
        await record_audit(session, "finance.report.created", "internal",
                           f"period={payload.period} type={payload.type}", request)
        return _to_dict(report)

    @staticmethod
    async def update_report(session: AsyncSession, report_id: str,
                            payload: ReportUpdate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        r = await repo.get_report(session, report_id)
        if not r:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "报表不存在")
        if r.status == "finalized":
            raise HTTPException(status.HTTP_409_CONFLICT, "已归档报表不可修改")
        for field in ("title", "data", "remark"):
            value = getattr(payload, field)
            if value is not None:
                setattr(r, field, value)
        r = await repo.update_report(session, r)
        await record_audit(session, "finance.report.updated", "internal",
                           f"report_id={report_id}", request)
        return _to_dict(r)

    @staticmethod
    async def finalize_report(session: AsyncSession, report_id: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        r = await repo.get_report(session, report_id)
        if not r:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "报表不存在")
        r.status = "finalized"
        r = await repo.update_report(session, r)
        await record_audit(session, "finance.report.finalized", "internal",
                           f"report_id={report_id}", request)
        return _to_dict(r)

    @staticmethod
    async def delete_report(session: AsyncSession, report_id: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        r = await repo.get_report(session, report_id)
        if not r:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "报表不存在")
        if r.status == "finalized":
            raise HTTPException(status.HTTP_409_CONFLICT, "已归档报表不可删除")
        await repo.delete_report(session, r)
        await record_audit(session, "finance.report.deleted", "internal",
                           f"report_id={report_id}", request)
        return {"deleted": True, "id": report_id}
