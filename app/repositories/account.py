from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, AccountType, AssetType, LedgerEntry


class AccountRepository:
    async def get_by_id(self, db: AsyncSession, account_id: int) -> Account | None:
        result = await db.execute(select(Account).where(Account.id == account_id))
        return result.scalar_one_or_none()

    async def get_user_by_external_id(self, db: AsyncSession, external_user_id: str) -> Account | None:
        result = await db.execute(
            select(Account).where(
                Account.type == AccountType.USER,
                Account.external_user_id == external_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_system_by_name(self, db: AsyncSession, name: str) -> Account | None:
        result = await db.execute(
            select(Account).where(
                Account.type == AccountType.SYSTEM,
                Account.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def get_balance(
        self,
        db: AsyncSession,
        account_id: int,
        asset_type_id: int,
    ) -> Decimal:
        result = await db.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                LedgerEntry.account_id == account_id,
                LedgerEntry.asset_type_id == asset_type_id,
            )
        )
        return result.scalar_one() or Decimal("0")

    async def lock_accounts_for_update(
        self,
        db: AsyncSession,
        account_ids: list[int],
    ) -> list[Account]:
        """Lock accounts by ID in ascending order to avoid deadlocks."""
        if not account_ids:
            return []
        ordered_ids = sorted(set(account_ids))
        result = await db.execute(
            select(Account).where(Account.id.in_(ordered_ids)).order_by(Account.id).with_for_update()
        )
        return list(result.scalars().all())


account_repo = AccountRepository()
