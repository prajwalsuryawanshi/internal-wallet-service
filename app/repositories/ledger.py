from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LedgerEntry, Transaction, TransactionType


class LedgerRepository:
    async def get_transaction_by_idempotency_key(
        self,
        db: AsyncSession,
        idempotency_key: str,
    ) -> Transaction | None:
        result = await db.execute(
            select(Transaction).where(Transaction.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def create_transaction_with_entries(
        self,
        db: AsyncSession,
        transaction_type: TransactionType,
        idempotency_key: str | None,
        entries: list[tuple[int, int, Decimal]],
    ) -> Transaction:
        """
        entries: list of (account_id, asset_type_id, amount) where amount is signed (+ credit, - debit).
        """
        tx = Transaction(type=transaction_type, idempotency_key=idempotency_key)
        db.add(tx)
        await db.flush()
        for account_id, asset_type_id, amount in entries:
            entry = LedgerEntry(
                transaction_id=tx.id,
                account_id=account_id,
                asset_type_id=asset_type_id,
                amount=amount,
            )
            db.add(entry)
        await db.flush()
        return tx


ledger_repo = LedgerRepository()
