"""财务凭证仓储层（含明细行）。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fin_voucher import FinVoucher
from app.models.fin_voucher_entry import FinVoucherEntry


async def get_voucher(session: AsyncSession, voucher_id: str) -> FinVoucher | None:
    result = await session.execute(select(FinVoucher).where(FinVoucher.id == voucher_id))
    return result.scalar_one_or_none()


async def get_voucher_by_no(session: AsyncSession, voucher_no: str) -> FinVoucher | None:
    result = await session.execute(select(FinVoucher).where(FinVoucher.voucher_no == voucher_no))
    return result.scalar_one_or_none()


async def list_vouchers(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    status: str | None = None, voucher_date: str | None = None,
) -> list[FinVoucher]:
    stmt = select(FinVoucher).order_by(FinVoucher.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(FinVoucher.status == status)
    if voucher_date:
        stmt = stmt.where(FinVoucher.voucher_date == voucher_date)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_vouchers(
    session: AsyncSession, status: str | None = None, voucher_date: str | None = None,
) -> int:
    stmt = select(func.count(FinVoucher.id))
    if status:
        stmt = stmt.where(FinVoucher.status == status)
    if voucher_date:
        stmt = stmt.where(FinVoucher.voucher_date == voucher_date)
    result = await session.execute(stmt)
    return result.scalar_one()


async def create_voucher(session: AsyncSession, voucher: FinVoucher) -> FinVoucher:
    session.add(voucher)
    await session.commit()
    await session.refresh(voucher)
    return voucher


async def update_voucher(session: AsyncSession, voucher: FinVoucher) -> FinVoucher:
    await session.commit()
    await session.refresh(voucher)
    return voucher


async def delete_voucher(session: AsyncSession, voucher: FinVoucher) -> None:
    await session.delete(voucher)
    await session.commit()


# ── 明细行 ──

async def list_entries(session: AsyncSession, voucher_id: str) -> list[FinVoucherEntry]:
    result = await session.execute(
        select(FinVoucherEntry)
        .where(FinVoucherEntry.voucher_id == voucher_id)
        .order_by(FinVoucherEntry.id)
    )
    return list(result.scalars().all())


async def add_entries(session: AsyncSession, entries: list[FinVoucherEntry]) -> None:
    session.add_all(entries)
    await session.commit()


async def delete_entries(session: AsyncSession, voucher_id: str) -> None:
    result = await session.execute(
        select(FinVoucherEntry).where(FinVoucherEntry.voucher_id == voucher_id)
    )
    for entry in result.scalars().all():
        await session.delete(entry)
    await session.commit()
