"""
Seed script: asset types, system accounts (Treasury), and two users with initial balances.
Run after DB is up and tables exist (e.g. after first app startup or migrations).
Usage: python -m scripts.seed
"""
import asyncio
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Use same URL as app or override
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/wallet",
)


async def seed():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        # Idempotent: only insert if empty (optional: truncate for clean re-seed)
        await conn.execute(text("""
            INSERT INTO asset_types (id, name, symbol)
            VALUES
                (1, 'Gold Coins', 'GOLD'),
                (2, 'Diamonds', 'DMND'),
                (3, 'Loyalty Points', 'PTS')
            ON CONFLICT (id) DO NOTHING
        """))
        # PostgreSQL: ensure sequence is past max id if we used explicit ids
        await conn.execute(text("""
            SELECT setval(pg_get_serial_sequence('asset_types', 'id'), (SELECT COALESCE(MAX(id), 1) FROM asset_types))
        """))

    # Use raw SQL for portability, or we could use ORM; for seed we keep it simple
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO accounts (id, type, external_user_id, name)
            VALUES
                (1, 'system', NULL, 'Treasury'),
                (2, 'user', 'user_alice', 'Alice'),
                (3, 'user', 'user_bob', 'Bob')
            ON CONFLICT (id) DO NOTHING
        """))
        await conn.execute(text("""
            SELECT setval(pg_get_serial_sequence('accounts', 'id'), (SELECT COALESCE(MAX(id), 1) FROM accounts))
        """))

    # Initial balances: give Treasury a large balance, then credit users from it via ledger
    # We do this by inserting transactions + ledger entries
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncSessionLocal() as session:
        # Check if we already have ledger entries for initial setup
        result = await session.execute(text("SELECT 1 FROM ledger_entries LIMIT 1"))
        if result.scalar_one_or_none() is not None:
            print("Ledger already has data, skipping initial balances.")
            return
        # Treasury: +10000 GOLD, +5000 DMND, +20000 PTS (we use negative entries to "fund" from nowhere for seed only)
        # In double-entry we need balanced entries: so we credit Treasury from a "seed" source.
        # For seed we'll create one system "Seed" account that we debit from (so Treasury gets credited).
        await session.execute(text("""
            INSERT INTO accounts (type, external_user_id, name) VALUES ('system', NULL, 'Seed')
        """))
        await session.flush()
        seed_id_result = await session.execute(text("SELECT id FROM accounts WHERE name = 'Seed'"))
        seed_id = seed_id_result.scalar_one()
        treasury_id = 1
        alice_id = 2
        bob_id = 3
        gold, diamonds, points = 1, 2, 3

        # Seed account: -10000 GOLD; Treasury: +10000 GOLD
        await session.execute(text("""
            INSERT INTO transactions (type, idempotency_key, created_at) VALUES ('bonus', 'seed_treasury_gold', NOW())
        """))
        await session.flush()
        tx_id = (await session.execute(text("SELECT id FROM transactions WHERE idempotency_key = 'seed_treasury_gold'"))).scalar_one()
        await session.execute(text("""
            INSERT INTO ledger_entries (transaction_id, account_id, asset_type_id, amount)
            VALUES (:tx, :seed, 1, -10000), (:tx, :treasury, 1, 10000)
        """), {"tx": tx_id, "seed": seed_id, "treasury": treasury_id})

        await session.execute(text("""
            INSERT INTO transactions (type, idempotency_key, created_at) VALUES ('bonus', 'seed_treasury_diamonds', NOW())
        """))
        await session.flush()
        tx_id = (await session.execute(text("SELECT id FROM transactions WHERE idempotency_key = 'seed_treasury_diamonds'"))).scalar_one()
        await session.execute(text("""
            INSERT INTO ledger_entries (transaction_id, account_id, asset_type_id, amount)
            VALUES (:tx, :seed, 2, -5000), (:tx, :treasury, 2, 5000)
        """), {"tx": tx_id, "seed": seed_id, "treasury": treasury_id})

        await session.execute(text("""
            INSERT INTO transactions (type, idempotency_key, created_at) VALUES ('bonus', 'seed_treasury_points', NOW())
        """))
        await session.flush()
        tx_id = (await session.execute(text("SELECT id FROM transactions WHERE idempotency_key = 'seed_treasury_points'"))).scalar_one()
        await session.execute(text("""
            INSERT INTO ledger_entries (transaction_id, account_id, asset_type_id, amount)
            VALUES (:tx, :seed, 3, -20000), (:tx, :treasury, 3, 20000)
        """), {"tx": tx_id, "seed": seed_id, "treasury": treasury_id})

        # Alice: 100 GOLD, 50 DMND, 500 PTS
        for asset_id, amt, key in [(1, 100, "seed_alice_gold"), (2, 50, "seed_alice_dmnd"), (3, 500, "seed_alice_pts")]:
            await session.execute(text("""
                INSERT INTO transactions (type, idempotency_key, created_at) VALUES ('bonus', :key, NOW())
            """), {"key": key})
            await session.flush()
            tx_id = (await session.execute(text("SELECT id FROM transactions WHERE idempotency_key = :key"), {"key": key})).scalar_one()
            await session.execute(text("""
                INSERT INTO ledger_entries (transaction_id, account_id, asset_type_id, amount)
                VALUES (:tx, :treasury, :asset, :neg), (:tx, :alice, :asset, :amt)
            """), {"tx": tx_id, "treasury": treasury_id, "alice": alice_id, "asset": asset_id, "neg": -amt, "amt": amt})

        # Bob: 80 GOLD, 30 DMND, 200 PTS
        for asset_id, amt, key in [(1, 80, "seed_bob_gold"), (2, 30, "seed_bob_dmnd"), (3, 200, "seed_bob_pts")]:
            await session.execute(text("""
                INSERT INTO transactions (type, idempotency_key, created_at) VALUES ('bonus', :key, NOW())
            """), {"key": key})
            await session.flush()
            tx_id = (await session.execute(text("SELECT id FROM transactions WHERE idempotency_key = :key"), {"key": key})).scalar_one()
            await session.execute(text("""
                INSERT INTO ledger_entries (transaction_id, account_id, asset_type_id, amount)
                VALUES (:tx, :treasury, :asset, :neg), (:tx, :bob, :asset, :amt)
            """), {"tx": tx_id, "treasury": treasury_id, "bob": bob_id, "asset": asset_id, "neg": -amt, "amt": amt})

        await session.commit()

    print("Seed completed: asset types, Treasury, Seed, user_alice, user_bob with initial balances.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
