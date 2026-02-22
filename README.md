# Internal Wallet Service (FastAPI)

A **wallet service** for application-specific credits/points (e.g. "Gold Coins", "Reward Points"). Closed-loop: credits exist only inside the app, are not real money, and cannot be transferred between users. Built with **FastAPI**, **PostgreSQL**, and a **double-entry ledger** for auditability.

## Features

- **REST API**: balance, top-up (purchase), bonus/incentive, spend
- **Double-entry ledger**: every movement is two (or more) entries that sum to zero; full audit trail
- **Concurrency-safe**: row-level locking in a consistent order to avoid deadlocks
- **Idempotency**: optional `idempotency_key` on write endpoints so retries are safe
- **Seeded data**: asset types, Treasury system account, two users (Alice, Bob) with initial balances

## Tech Stack

- **FastAPI** – async Python API, automatic OpenAPI docs, type-safe request/response
- **SQLAlchemy 2 (async)** – ORM with asyncpg for PostgreSQL
- **PostgreSQL** – ACID transactions, row locking, suitable for high traffic

**Why FastAPI:** Async end-to-end fits I/O-bound wallet operations; built-in validation and OpenAPI; easy to test and deploy.

## Quick Start

### Option 1: Docker (recommended)

```bash
docker compose up -d
```

- **Database**: PostgreSQL on `localhost:5432` (user `postgres`, password `postgres`, db `wallet`)
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **Seed**: runs automatically after the app is healthy (asset types, Treasury, `user_alice`, `user_bob` with balances)

### Option 3: Deploy on Render

1. Fork or push this repo to GitHub and connect it to [Render](https://render.com).
2. Use the **Blueprint** (Infrastructure as Code): in the Render dashboard, choose "New" → "Blueprint", connect the repo; Render will read `render.yaml` and create a Web Service + PostgreSQL.
3. Or create manually: **New → Web Service**, connect repo, set **Environment** to **Docker**. Add a **PostgreSQL** database and set `DATABASE_URL` to the DB’s internal connection string (Render uses `postgres://`; the app converts it to `postgresql+asyncpg://`).
4. After deploy, run the seed once (e.g. from your machine with `DATABASE_URL` set to the Render DB URL): `uv run python -m scripts.seed`.

### Option 2: Local run

1. **Create and start PostgreSQL** (e.g. local install or Docker: `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=wallet postgres:16-alpine`).

2. **Install dependencies** (e.g. with [uv](https://github.com/astral-sh/uv)):
   ```bash
   uv sync
   ```

3. **Set database URL** (optional if already default):
   ```bash
   set DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/wallet
   ```

4. **Run the app** (creates tables on startup):
   ```bash
   uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Seed data** (in another terminal):
   ```bash
   uv run python -m scripts.seed
   ```

### Seed data

- **Asset types**: Gold Coins (GOLD), Diamonds (DMND), Loyalty Points (PTS)
- **System account**: Treasury (source/sink for credits)
- **Users**: `user_alice`, `user_bob` (external_user_id) with initial balances

You can also run the raw SQL for base data only: `psql -U postgres -d wallet -f seed.sql`. For full initial balances, use the Python seed: `python -m scripts.seed`.

## API Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/wallets/users/{external_user_id}/balance?asset_type_id=1` | Get balance for user and asset type |
| POST | `/api/v1/wallets/users/{external_user_id}/top-up` | Credit wallet (e.g. after purchase) |
| POST | `/api/v1/wallets/users/{external_user_id}/bonus` | Issue free credits (e.g. referral) |
| POST | `/api/v1/wallets/users/{external_user_id}/spend` | Debit wallet (e.g. in-app purchase) |

**Body for POST** (JSON):

```json
{
  "amount": "100.00",
  "asset_type_id": 1,
  "idempotency_key": "optional-unique-key"
}
```

**Example – get balance:**

```bash
curl "http://localhost:8000/api/v1/wallets/users/user_alice/balance?asset_type_id=1"
```

**Example – top-up then spend:**

```bash
curl -X POST "http://localhost:8000/api/v1/wallets/users/user_alice/top-up" \
  -H "Content-Type: application/json" \
  -d '{"amount": 50, "asset_type_id": 1}'

curl -X POST "http://localhost:8000/api/v1/wallets/users/user_alice/spend" \
  -H "Content-Type: application/json" \
  -d '{"amount": 30, "asset_type_id": 1}'
```

## Concurrency Strategy

1. **Row-level locking**  
   For every write (top-up, bonus, spend) we lock the **accounts** involved (Treasury and user) using `SELECT ... FOR UPDATE` so two concurrent transactions cannot modify the same account at the same time.

2. **Consistent lock order (deadlock avoidance)**  
   We always lock accounts in **ascending `account_id`** (e.g. Treasury then user, or user then Treasury, by id). So every transaction acquires locks in the same order and **deadlocks** between two such transactions are avoided.

3. **Balance from ledger**  
   Balance is computed as `SUM(amount)` over `ledger_entries` for that account and asset type. We do not only “update a balance column”; the ledger is the source of truth. Writes add new ledger rows inside the same DB transaction as the locks, so balance stays correct under concurrency.

4. **Idempotency**  
   Write endpoints accept an optional `idempotency_key`. If the same key is sent again, we return the **existing** transaction result (same `transaction_id`, current balance) without creating a new transaction. This prevents double credits or double debits on retries.

## Project Layout

```
assignment/
├── app/
│   ├── main.py          # FastAPI app, table creation on startup
│   ├── config.py        # Settings (e.g. DATABASE_URL)
│   ├── database.py      # Async engine and session
│   ├── models/          # SQLAlchemy: Account, AssetType, Transaction, LedgerEntry
│   ├── repositories/    # DB access: account_repo, ledger_repo
│   ├── services/        # wallet_service (top-up, bonus, spend)
│   ├── schemas/         # Pydantic request/response
│   └── api/routes/      # REST endpoints
├── scripts/
│   └── seed.py          # Full seed (asset types, accounts, initial balances)
├── seed.sql             # SQL seed (asset types + accounts only)
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## License

Assignment project – use as required by the assignment terms.
