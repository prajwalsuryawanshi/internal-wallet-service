# Internal Wallet Service — Technical Architecture & Design Documentation

This document explains the low-level design decisions, concurrency handling, and implementation details of the Internal Wallet Service. It is intended for technical review and interview preparation.

---

## Table of Contents

1. [Problem Context](#1-problem-context)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Data Model & Double-Entry Ledger](#3-data-model--double-entry-ledger)
4. [Concurrency & Race Conditions](#4-concurrency--race-conditions)
5. [Idempotency](#5-idempotency)
6. [Technology Decisions](#6-technology-decisions)
7. [Request Flow](#7-request-flow)
8. [Trade-offs & Alternatives](#8-trade-offs--alternatives)

---

## 1. Problem Context

### What We Built

A **closed-loop wallet service** for application-specific credits (e.g., "Gold Coins", "Reward Points"). These credits:

- Exist only inside the application
- Are not real money or cryptocurrency
- Cannot be transferred between users (unlike payment apps)
- Must maintain **strict data integrity**: every credit added or spent must be recorded correctly, balances must never go negative or out of sync, and no transactions can be lost—even under heavy traffic or system failures.

### Core Flows

1. **Wallet Top-up (Purchase)**: User buys credits with real money → credits added to their wallet.
2. **Bonus/Incentive**: System issues free credits (e.g., referral bonus).
3. **Purchase/Spend**: User spends credits within the app (e.g., in-app purchase).

### Critical Constraints

- **Concurrency & Race Conditions**: Multiple requests must not corrupt data.
- **Idempotency**: Retries must not double-credit or double-debit.

---

## 2. High-Level Architecture

```
┌─────────────┐     HTTP      ┌──────────────────┐     SQL      ┌─────────────┐
│   Client    │ ────────────► │  FastAPI (async)  │ ────────────►│  PostgreSQL │
└─────────────┘               │  - Routes         │              │  - ACID      │
                              │  - Services       │              │  - Row locks │
                              │  - Repositories   │              │  - Ledger    │
                              └──────────────────┘               └─────────────┘
```

**Layers:**

| Layer | Responsibility |
|-------|----------------|
| **Routes** | HTTP handling, validation, error mapping |
| **Services** | Business logic (top-up, bonus, spend), orchestration |
| **Repositories** | Database access, queries, locking |
| **Models** | SQLAlchemy ORM, schema definition |

---

## 3. Data Model & Double-Entry Ledger

### Why Double-Entry?

Instead of a single `balance` column that we update with `balance += amount`, we use a **ledger-based** approach:

- Every movement is recorded as **ledger entries**.
- Each transaction has **at least two entries** that **sum to zero** (debit one account, credit another).
- Balance = `SUM(ledger_entries.amount)` for that account and asset type.

**Benefits:**

1. **Auditability**: Full history of every movement.
2. **No lost updates**: We append rows instead of updating a single cell.
3. **Consistency**: Double-entry enforces that credits don’t appear or disappear; they move between accounts.

### Schema Overview

```
asset_types          accounts              transactions           ledger_entries
─────────────        ─────────             ────────────           ───────────────
id (PK)              id (PK)               id (PK)               id (PK)
name                 type (user/system)   type (top_up/bonus/   transaction_id (FK)
symbol               external_user_id     spend)                 account_id (FK)
                     name                 idempotency_key        asset_type_id (FK)
                                        created_at              amount (+/-)
```

### Ledger Entry Semantics

- **Positive amount** = credit (money in)
- **Negative amount** = debit (money out)
- For each transaction, `SUM(entries.amount) = 0` (balanced).

### Example: User Spends 30 Gold Coins

| account_id | asset_type_id | amount |
|------------|---------------|--------|
| user_alice | 1 (GOLD)      | -30    |
| Treasury   | 1 (GOLD)      | +30    |

User debited, Treasury credited. Sum = 0.

---

## 4. Concurrency & Race Conditions

### The Problem

Two concurrent requests for the same user:

- **Request A**: Spend 80 (balance = 100)
- **Request B**: Spend 50 (balance = 100)

Without protection, both could read 100, both could succeed, and the user would end up with 100 - 80 - 50 = -30 (invalid).

### Our Solution: Row-Level Locking + Consistent Order

#### 4.1 Row-Level Locking (`SELECT ... FOR UPDATE`)

Before modifying ledger entries, we **lock the affected account rows**:

```python
# In account_repo.lock_accounts_for_update
ordered_ids = sorted(set(account_ids))
result = await db.execute(
    select(Account).where(Account.id.in_(ordered_ids))
    .order_by(Account.id)
    .with_for_update()
)
```

- `FOR UPDATE` blocks other transactions from modifying those rows until we commit or rollback.
- The second request waits until the first releases the lock.

#### 4.2 Consistent Lock Order (Deadlock Avoidance)

We **always lock accounts in ascending `account_id`**:

- Transaction 1: locks Treasury (id=1), then User A (id=2)
- Transaction 2: locks Treasury (id=1), then User B (id=3)

If we locked in different orders (e.g., A locks User then Treasury, B locks Treasury then User), we could get:

- A holds User, waits for Treasury
- B holds Treasury, waits for User  
→ **Deadlock**

By always locking in `ORDER BY id`, every transaction acquires locks in the same order → **no circular wait** → **no deadlock**.

#### 4.3 Balance Check Inside Lock

For **spend**, we:

1. Lock both accounts (user + Treasury)
2. Compute balance = `SUM(ledger_entries)`
3. If balance < amount → raise `InsufficientBalanceError`
4. Insert ledger entries
5. Commit

All of this happens in a single database transaction, so no other transaction can change the balance between our check and our insert.

#### 4.4 Isolation Level

We use PostgreSQL’s default **READ COMMITTED** (or higher if configured). With `FOR UPDATE`, we get the necessary isolation for correct balance checks and updates.

---

## 5. Idempotency

### The Problem

A client sends a top-up request, the server processes it, but the response is lost (network timeout, client crash). The client retries with the same request. Without idempotency, the user would be credited **twice**.

### Our Solution: Idempotency Key

- Client sends an optional `idempotency_key` (e.g., UUID) with each write request.
- We store it in `transactions.idempotency_key` (unique).
- On a new request:
  1. If `idempotency_key` is provided, check if a transaction with that key already exists.
  2. If yes → return the **existing** transaction result (same `transaction_id`, current balance). Do **not** create a new transaction.
  3. If no → proceed normally and store the key on the new transaction.

**Important:** Idempotency check happens **before** acquiring locks, so we avoid locking when we’re just returning a cached result.

---

## 6. Technology Decisions

### FastAPI

- **Async end-to-end**: I/O-bound wallet operations benefit from non-blocking DB calls.
- **Automatic OpenAPI**: `/docs` for free, good for integration.
- **Pydantic**: Request/response validation, type safety.

### PostgreSQL

- ACID transactions.
- Row-level locking (`FOR UPDATE`).
- Mature, reliable, suitable for financial-style workloads.

### SQLAlchemy 2 (Async)

- Async support via `asyncpg`.
- Clear separation of models, repositories, and services.
- `with_for_update()` for locking.

### Why Not a Single Balance Column?

- **Lost updates** under concurrency.
- **No audit trail**.
- **Harder to debug** discrepancies.

### Why Not Event Sourcing?

- Overkill for this scope.
- Double-entry ledger already gives auditability.
- Simpler operational model.

---

## 7. Request Flow

### Example: POST /spend

```
1. Route receives request (external_user_id, amount, asset_type_id, idempotency_key)
2. Resolve user account by external_user_id → 404 if not found
3. Service.spend():
   a. If idempotency_key: check for existing transaction → return if found
   b. Get Treasury system account
   c. lock_accounts_for_update([user_id, treasury_id])  # sorted by id
   d. get_balance(user, asset_type)
   e. If balance < amount → InsufficientBalanceError (402)
   f. create_transaction_with_entries(SPEND, entries: user -amount, treasury +amount)
   g. get_balance again → return (tx_id, new_balance)
4. get_db commits (or rolls back on exception)
5. Return JSON { transaction_id, new_balance }
```

---

## 8. Trade-offs & Alternatives

| Decision | Alternative | Why We Chose This |
|----------|-------------|-------------------|
| Double-entry ledger | Single balance column | Auditability, no lost updates |
| Row-level locking | Optimistic locking (version column) | Simpler, fewer retries |
| Lock by account_id order | Ad-hoc order | Deadlock avoidance |
| Idempotency key in DB | Redis/cache | Persistent, survives restarts |
| PostgreSQL | MySQL, SQLite | Strong ACID, good locking support |
| FastAPI async | Sync Flask/Django | Better throughput for I/O-bound workload |

---

## Summary

- **Data integrity**: Double-entry ledger, balance = sum of entries.
- **Concurrency**: Row-level locking (`FOR UPDATE`) in consistent order to avoid deadlocks.
- **Idempotency**: Unique `idempotency_key` to prevent double-processing on retries.
- **Layering**: Routes → Services → Repositories → DB for clear separation of concerns.
