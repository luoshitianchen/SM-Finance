"""财务科目仓储层。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fin_account import FinAccount


async def get_account(session: AsyncSession, account_id: str) -> FinAccount | None:
    result = await session.execute(select(FinAccount).where(FinAccount.id == account_id))
    return result.scalar_one_or_none()


async def get_account_by_code(session: AsyncSession, code: str) -> FinAccount | None:
    result = await session.execute(select(FinAccount).where(FinAccount.code == code))
    return result.scalar_one_or_none()


async def list_accounts(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    category: str | None = None, keyword: str | None = None,
) -> list[FinAccount]:
    stmt = select(FinAccount).order_by(FinAccount.code).limit(limit).offset(offset)
    if category:
        stmt = stmt.where(FinAccount.category == category)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(FinAccount.name.like(like), FinAccount.code.like(like)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_accounts(
    session: AsyncSession, category: str | None = None, keyword: str | None = None,
) -> int:
    stmt = select(func.count(FinAccount.id))
    if category:
        stmt = stmt.where(FinAccount.category == category)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(FinAccount.name.like(like), FinAccount.code.like(like)))
    result = await session.execute(stmt)
    return result.scalar_one()


async def create_account(session: AsyncSession, account: FinAccount) -> FinAccount:
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


async def update_account(session: AsyncSession, account: FinAccount) -> FinAccount:
    await session.commit()
    await session.refresh(account)
    return account


async def delete_account(session: AsyncSession, account: FinAccount) -> None:
    await session.delete(account)
    await session.commit()
