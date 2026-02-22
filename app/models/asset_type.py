from __future__ import annotations

from typing import TYPE_CHECKING
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.ledger import LedgerEntry


class AssetType(Base):
    __tablename__ = "asset_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)

    ledger_entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="asset_type")

    def __repr__(self) -> str:
        return f"AssetType(id={self.id}, name={self.name!r}, symbol={self.symbol!r})"
