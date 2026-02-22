-- Seed data for Internal Wallet Service (PostgreSQL)
-- Run after tables are created (e.g. by starting the app once, or via Alembic).
-- For full seed including initial balances, use: python -m scripts.seed

-- Asset types
INSERT INTO asset_types (id, name, symbol)
VALUES
    (1, 'Gold Coins', 'GOLD'),
    (2, 'Diamonds', 'DMND'),
    (3, 'Loyalty Points', 'PTS')
ON CONFLICT (id) DO NOTHING;

SELECT setval(pg_get_serial_sequence('asset_types', 'id'), (SELECT COALESCE(MAX(id), 1) FROM asset_types));

-- System and user accounts
INSERT INTO accounts (id, type, external_user_id, name)
VALUES
    (1, 'system', NULL, 'Treasury'),
    (2, 'user', 'user_alice', 'Alice'),
    (3, 'user', 'user_bob', 'Bob')
ON CONFLICT (id) DO NOTHING;

SELECT setval(pg_get_serial_sequence('accounts', 'id'), (SELECT COALESCE(MAX(id), 1) FROM accounts));

-- Note: Initial balances for users are best added via the Python seed script (scripts/seed.py)
-- which creates double-entry ledger transactions. Run: python -m scripts.seed
