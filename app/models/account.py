from __future__ import annotations

import enum
from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AccountType(str, enum.Enum):
    USER = "user"
    SYSTEM = "system"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    external_user_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    ledger_entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="account")

    def __repr__(self) -> str:
        return f"Account(id={self.id}, type={self.type.value}, name={self.name!r})"
