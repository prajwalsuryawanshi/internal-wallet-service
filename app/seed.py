"""ORM-based seed for SQLite and PostgreSQL compatibility."""
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, AccountType, AssetType, LedgerEntry, Transaction, TransactionType


async def run_seed(db: AsyncSession) -> str:
    """Seed asset types, accounts, and initial balances. Idempotent. Returns status message."""
    # Asset types
    r = await db.execute(select(AssetType).limit(1))
    if r.scalar_one_or_none() is None:
        for name, symbol in [("Gold Coins", "GOLD"), ("Diamonds", "DMND"), ("Loyalty Points", "PTS")]:
            db.add(AssetType(name=name, symbol=symbol))
        await db.flush()

    # Accounts: Treasury, Alice, Bob
    r = await db.execute(select(Account).where(Account.name == "Treasury").limit(1))
    if r.scalar_one_or_none() is None:
        db.add(Account(type=AccountType.SYSTEM, name="Treasury"))
        db.add(Account(type=AccountType.USER, external_user_id="user_alice", name="Alice"))
        db.add(Account(type=AccountType.USER, external_user_id="user_bob", name="Bob"))
        await db.flush()

    # Ledger entries - skip if already seeded
    r = await db.execute(select(LedgerEntry).limit(1))
    if r.scalar_one_or_none() is not None:
        return "Already seeded"

    treasury = (await db.execute(select(Account).where(Account.name == "Treasury"))).scalar_one()
    alice = (await db.execute(select(Account).where(Account.external_user_id == "user_alice"))).scalar_one()
    bob = (await db.execute(select(Account).where(Account.external_user_id == "user_bob"))).scalar_one()
    gold, diamonds, points = 1, 2, 3

    async def add_bonus(from_acc: Account, to_acc: Account, asset_id: int, amount: Decimal):
        tx = Transaction(type=TransactionType.BONUS)
        db.add(tx)
        await db.flush()
        db.add(LedgerEntry(transaction_id=tx.id, account_id=from_acc.id, asset_type_id=asset_id, amount=-amount))
        db.add(LedgerEntry(transaction_id=tx.id, account_id=to_acc.id, asset_type_id=asset_id, amount=amount))

    # Seed account to fund Treasury
    seed_acc = Account(type=AccountType.SYSTEM, name="Seed")
    db.add(seed_acc)
    await db.flush()

    await add_bonus(seed_acc, treasury, gold, Decimal("10000"))
    await add_bonus(seed_acc, treasury, diamonds, Decimal("5000"))
    await add_bonus(seed_acc, treasury, points, Decimal("20000"))
    await add_bonus(treasury, alice, gold, Decimal("100"))
    await add_bonus(treasury, alice, diamonds, Decimal("50"))
    await add_bonus(treasury, alice, points, Decimal("500"))
    await add_bonus(treasury, bob, gold, Decimal("80"))
    await add_bonus(treasury, bob, diamonds, Decimal("30"))
    await add_bonus(treasury, bob, points, Decimal("200"))

    await db.flush()
    return "Seeded: asset types, Treasury, user_alice, user_bob with initial balances"
