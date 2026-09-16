"""财务报表仓储层。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fin_report import FinReport


async def get_report(session: AsyncSession, report_id: str) -> FinReport | None:
    result = await session.execute(select(FinReport).where(FinReport.id == report_id))
    return result.scalar_one_or_none()


async def get_report_by_period_type(
    session: AsyncSession, period: str, report_type: str,
) -> FinReport | None:
    result = await session.execute(
        select(FinReport)
        .where(FinReport.period == period, FinReport.type == report_type)
    )
    return result.scalar_one_or_none()


async def list_reports(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    report_type: str | None = None, period: str | None = None,
) -> list[FinReport]:
    stmt = select(FinReport).order_by(FinReport.created_at.desc()).limit(limit).offset(offset)
    if report_type:
        stmt = stmt.where(FinReport.type == report_type)
    if period:
        stmt = stmt.where(FinReport.period == period)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_reports(
    session: AsyncSession, report_type: str | None = None, period: str | None = None,
) -> int:
    stmt = select(func.count(FinReport.id))
    if report_type:
        stmt = stmt.where(FinReport.type == report_type)
    if period:
        stmt = stmt.where(FinReport.period == period)
    result = await session.execute(stmt)
    return result.scalar_one()


async def create_report(session: AsyncSession, report: FinReport) -> FinReport:
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def update_report(session: AsyncSession, report: FinReport) -> FinReport:
    await session.commit()
    await session.refresh(report)
    return report


async def delete_report(session: AsyncSession, report: FinReport) -> None:
    await session.delete(report)
    await session.commit()
