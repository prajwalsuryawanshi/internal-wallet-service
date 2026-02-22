"""
Wallet service: top-up, bonus, spend with double-entry ledger,
row-level locking for concurrency, and idempotency.
"""
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AccountType, TransactionType
from app.repositories import account_repo, ledger_repo


class InsufficientBalanceError(ValueError):
    pass


class WalletService:
    SYSTEM_TREASURY_NAME = "Treasury"

    async def get_balance(
        self,
        db: AsyncSession,
        account_id: int,
        asset_type_id: int,
    ) -> Decimal:
        return await account_repo.get_balance(db, account_id, asset_type_id)

    async def _lock_and_ensure_balance(
        self,
        db: AsyncSession,
        user_account_id: int,
        system_account_id: int,
        asset_type_id: int,
        amount: Decimal,
    ) -> None:
        """Lock both accounts in consistent order (deadlock avoidance), then check balance."""
        await account_repo.lock_accounts_for_update(db, [user_account_id, system_account_id])
        balance = await account_repo.get_balance(db, user_account_id, asset_type_id)
        if balance < amount:
            raise InsufficientBalanceError(
                f"Insufficient balance: have {balance}, need {amount}"
            )

    async def top_up(
        self,
        db: AsyncSession,
        user_account_id: int,
        asset_type_id: int,
        amount: Decimal,
        idempotency_key: str | None = None,
    ) -> tuple[int, Decimal]:
        """
        User purchases credits (money already received by payment system).
        Treasury is debited, user is credited.
        Returns (transaction_id, new_balance).
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if idempotency_key:
            existing = await ledger_repo.get_transaction_by_idempotency_key(db, idempotency_key)
            if existing:
                new_balance = await self.get_balance(db, user_account_id, asset_type_id)
                return existing.id, new_balance
        system = await account_repo.get_system_by_name(db, self.SYSTEM_TREASURY_NAME)
        if not system:
            raise ValueError("System Treasury account not found")
        await account_repo.lock_accounts_for_update(db, [system.id, user_account_id])
        entries = [
            (system.id, asset_type_id, -amount),
            (user_account_id, asset_type_id, amount),
        ]
        tx = await ledger_repo.create_transaction_with_entries(
            db, TransactionType.TOP_UP, idempotency_key, entries
        )
        new_balance = await self.get_balance(db, user_account_id, asset_type_id)
        return tx.id, new_balance

    async def bonus(
        self,
        db: AsyncSession,
        user_account_id: int,
        asset_type_id: int,
        amount: Decimal,
        idempotency_key: str | None = None,
    ) -> tuple[int, Decimal]:
        """
        System issues free credits (e.g. referral bonus).
        Treasury debited, user credited.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if idempotency_key:
            existing = await ledger_repo.get_transaction_by_idempotency_key(db, idempotency_key)
            if existing:
                new_balance = await self.get_balance(db, user_account_id, asset_type_id)
                return existing.id, new_balance
        system = await account_repo.get_system_by_name(db, self.SYSTEM_TREASURY_NAME)
        if not system:
            raise ValueError("System Treasury account not found")
        await account_repo.lock_accounts_for_update(db, [system.id, user_account_id])
        entries = [
            (system.id, asset_type_id, -amount),
            (user_account_id, asset_type_id, amount),
        ]
        tx = await ledger_repo.create_transaction_with_entries(
            db, TransactionType.BONUS, idempotency_key, entries
        )
        new_balance = await self.get_balance(db, user_account_id, asset_type_id)
        return tx.id, new_balance

    async def spend(
        self,
        db: AsyncSession,
        user_account_id: int,
        asset_type_id: int,
        amount: Decimal,
        idempotency_key: str | None = None,
    ) -> tuple[int, Decimal]:
        """
        User spends credits (e.g. in-app purchase).
        User debited, Treasury credited. Fails if balance insufficient.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if idempotency_key:
            existing = await ledger_repo.get_transaction_by_idempotency_key(db, idempotency_key)
            if existing:
                new_balance = await self.get_balance(db, user_account_id, asset_type_id)
                return existing.id, new_balance
        system = await account_repo.get_system_by_name(db, self.SYSTEM_TREASURY_NAME)
        if not system:
            raise ValueError("System Treasury account not found")
        await self._lock_and_ensure_balance(
            db, user_account_id, system.id, asset_type_id, amount
        )
        entries = [
            (user_account_id, asset_type_id, -amount),
            (system.id, asset_type_id, amount),
        ]
        tx = await ledger_repo.create_transaction_with_entries(
            db, TransactionType.SPEND, idempotency_key, entries
        )
        new_balance = await self.get_balance(db, user_account_id, asset_type_id)
        return tx.id, new_balance


wallet_service = WalletService()
