# Interview Questions & Answers — Internal Wallet Service

This document contains probable interview questions related to the Internal Wallet Service assignment, the technologies used, and the design decisions made. Use it to prepare for backend engineering interviews.

---

## 1. Project & Requirements

### Q1.1: What problem does this wallet service solve?

**Answer:** It’s a closed-loop wallet for application-specific credits (e.g., Gold Coins, Reward Points) used in gaming or loyalty systems. Credits exist only inside the app, are not real money, and cannot be transferred between users. The main challenge is **data integrity**: every credit added or spent must be recorded correctly, balances must never go negative or out of sync, and no transactions can be lost—even under high traffic or failures.

### Q1.2: What are the three core flows you implemented?

**Answer:**

1. **Wallet Top-up (Purchase)**: User buys credits with real money. Treasury is debited, user is credited.
2. **Bonus/Incentive**: System issues free credits (e.g., referral). Same double-entry: Treasury debited, user credited.
3. **Purchase/Spend**: User spends credits in the app. User debited, Treasury credited. Fails with 402 if balance is insufficient.

---

## 2. Concurrency & Race Conditions

### Q2.1: How did you handle race conditions when two users (or the same user) perform concurrent transactions?

**Answer:** We use **row-level locking** with `SELECT ... FOR UPDATE` on the affected account rows. Before inserting ledger entries, we lock both the user account and the Treasury account. The second transaction waits until the first commits or rolls back. Balance is computed and checked **inside** the same transaction, so no other transaction can change it between our check and our insert.

### Q2.2: How did you avoid deadlocks?

**Answer:** We always acquire locks in a **consistent order**—by ascending `account_id`. So every transaction locks Treasury (id=1) before User A (id=2), and User A before User B (id=3). Deadlocks occur when two transactions hold locks in different orders and wait for each other. With a fixed order, there is no circular wait, so no deadlocks.

### Q2.3: What would happen if you didn’t use a consistent lock order?

**Answer:** Transaction A could lock User 2, then wait for Treasury. Transaction B could lock Treasury, then wait for User 2. Each holds a lock the other needs → deadlock. PostgreSQL would eventually detect it and abort one transaction.

### Q2.4: Why not use optimistic locking (e.g., a version column)?

**Answer:** Optimistic locking works by reading a version, making changes, and updating only if the version hasn’t changed. Under contention, you get many retries. For a wallet with frequent concurrent updates, **pessimistic locking** (row locks) is simpler and avoids retry logic. We chose it for clarity and predictability.

---

## 3. Idempotency

### Q3.1: What is idempotency and why is it important for this service?

**Answer:** Idempotency means that performing the same operation multiple times has the same effect as performing it once. For wallet writes, if a client retries after a timeout, we must not credit or debit twice. We use an **idempotency key** (e.g., UUID) sent by the client. If we’ve already processed that key, we return the existing result instead of creating a new transaction.

### Q3.2: Where do you store the idempotency key?

**Answer:** In the `transactions` table as a unique column. That way it survives restarts and doesn’t depend on Redis or another cache. The trade-off is an extra DB lookup before each write, which is acceptable for this use case.

### Q3.3: What happens if the same idempotency key is sent for different operations (e.g., top-up vs spend)?

**Answer:** The key is globally unique per transaction. The first request wins. A second request with the same key returns the result of the first, regardless of the new operation type. So the client must use a **new** idempotency key for each distinct operation.

---

## 4. Double-Entry Ledger

### Q4.1: Why use a double-entry ledger instead of a simple balance column?

**Answer:**

1. **Auditability**: Every movement is recorded; you can trace where credits came from and went.
2. **No lost updates**: We append rows instead of updating a single balance cell, which avoids race conditions on that cell.
3. **Consistency**: Each transaction’s entries sum to zero, so credits don’t appear or disappear; they move between accounts.

### Q4.2: How do you compute a user’s balance?

**Answer:** Balance = `SUM(ledger_entries.amount)` for that `account_id` and `asset_type_id`. Positive amounts are credits, negative are debits. We don’t cache balance in a column; the ledger is the source of truth.

### Q4.3: What guarantees does double-entry give you?

**Answer:** For every transaction, the sum of all ledger entries is zero. So the total credits in the system are conserved. If we sum all entries across all accounts for an asset type, we get zero (or a constant, depending on how we model the “source” of credits).

---

## 5. Technology Choices

### Q5.1: Why FastAPI over Flask or Django?

**Answer:** FastAPI is async-native, which fits I/O-bound wallet operations. It provides automatic OpenAPI docs, Pydantic validation, and good performance. For a small, focused API, it’s a good fit.

### Q5.2: Why PostgreSQL over MySQL or SQLite?

**Answer:** PostgreSQL has strong ACID guarantees and good support for row-level locking. SQLite doesn’t handle high concurrency as well. MySQL is viable, but PostgreSQL is commonly used for financial-style workloads.

### Q5.3: Why async SQLAlchemy?

**Answer:** Async allows the server to handle other requests while waiting on the database. For I/O-bound workloads, this improves throughput. We use `asyncpg` as the async PostgreSQL driver.

### Q5.4: Why not use Redis for balance or idempotency?

**Answer:** For balance, we need strong consistency and auditability, which a relational DB with a ledger provides. For idempotency, storing the key in the DB keeps the system simpler and avoids another component. Redis could be added later for caching or rate limiting if needed.

---

## 6. Database & SQL

### Q6.1: What does `SELECT ... FOR UPDATE` do?

**Answer:** It locks the selected rows for the duration of the transaction. Other transactions that try to lock the same rows will block until we commit or rollback. It’s used for pessimistic concurrency control.

### Q6.2: What isolation level are you using?

**Answer:** PostgreSQL’s default is **READ COMMITTED**. With `FOR UPDATE`, we get the isolation we need for correct balance checks and updates. For stricter guarantees, we could use **REPEATABLE READ** or **SERIALIZABLE**, but that can increase lock contention and deadlock risk.

### Q6.3: How would you add an index to speed up balance queries?

**Answer:** We have a composite index on `(account_id, asset_type_id)` for `ledger_entries`. That supports `SUM(amount) WHERE account_id = ? AND asset_type_id = ?` efficiently.

---

## 7. API Design

### Q7.1: Why use `external_user_id` instead of internal account ID in the API?

**Answer:** The API is designed to be called by other services that know users by their external identifier (e.g., from an auth system). We resolve `external_user_id` to our internal `account_id` inside the service. This keeps our internal schema decoupled from external systems.

### Q7.2: Why return 402 for insufficient balance?

**Answer:** 402 Payment Required is a standard HTTP status for “payment could not be processed.” It clearly signals that the spend failed due to insufficient funds, as opposed to a generic 400 or 500.

---

## 8. Scalability & Production

### Q8.1: How would you scale this service?

**Answer:**

1. **Read replicas**: Balance reads can go to replicas; writes stay on the primary.
2. **Connection pooling**: We use SQLAlchemy’s pool; tuning `pool_size` and `max_overflow` helps under load.
3. **Caching**: Cache balance reads with short TTL; invalidate on writes. Must be careful with consistency.
4. **Sharding**: By `account_id` or `external_user_id` if we outgrow a single DB.

### Q8.2: How would you add rate limiting?

**Answer:** Use a middleware (e.g., slowapi) or a reverse proxy (e.g., nginx) to limit requests per user or IP. For stricter limits, use Redis-based rate limiting.

### Q8.3: How would you monitor this in production?

**Answer:** Log request/response, latency, and errors. Add metrics for transaction volume, balance checks, and error rates. Use distributed tracing for debugging. Alert on high error rates or latency.

---

## 9. Testing

### Q9.1: How would you test for race conditions?

**Answer:** Use concurrent test runners (e.g., pytest with multiple workers or asyncio tasks) that perform many spend operations on the same account with a balance that allows only some to succeed. Assert that the final balance is correct and no negative balances occur.

### Q9.2: How would you test idempotency?

**Answer:** Send the same request (including idempotency key) twice. Assert that the second response returns the same `transaction_id` and that only one transaction exists in the DB.

---

## 10. Design Decisions Summary

| Topic | Decision | Reason |
|-------|----------|--------|
| Ledger | Double-entry | Auditability, no lost updates |
| Concurrency | Row-level locking | Simple, predictable |
| Deadlocks | Consistent lock order | Avoid circular wait |
| Idempotency | Key in DB | Persistent, no extra infra |
| Balance | Computed from ledger | Single source of truth |
| Framework | FastAPI async | Good fit for I/O-bound API |
| Database | PostgreSQL | ACID, locking support |

---

*Use this document alongside `ARCHITECTURE.md` for a complete picture of the system and to prepare for technical discussions.*
