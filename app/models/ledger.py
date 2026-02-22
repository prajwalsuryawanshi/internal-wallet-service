from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, Enum, Numeric, String, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.asset_type import AssetType


class TransactionType(str, enum.Enum):
    TOP_UP = "top_up"
    BONUS = "bonus"
    SPEND = "spend"


class Transaction(Base):
    """Parent record for a double-entry transaction. Sum of ledger entries = 0."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=text("now()"),
    )

    entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="transaction", order_by="LedgerEntry.id")


class LedgerEntry(Base):
    """Single line in the ledger. Positive amount = credit, negative = debit."""

    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    asset_type_id: Mapped[int] = mapped_column(ForeignKey("asset_types.id", ondelete="RESTRICT"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)

    transaction: Mapped[Transaction] = relationship(back_populates="entries")
    account: Mapped["Account"] = relationship(back_populates="ledger_entries")
    asset_type: Mapped["AssetType"] = relationship(back_populates="ledger_entries")

    __table_args__ = (
        Index("ix_ledger_account_asset", "account_id", "asset_type_id"),
    )
