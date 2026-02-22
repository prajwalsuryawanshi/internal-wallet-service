from decimal import Decimal
from pydantic import BaseModel, Field


class TransactionRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Amount to credit or debit")
    asset_type_id: int = Field(..., description="Asset type (e.g. Gold Coins)")
    idempotency_key: str | None = Field(None, description="Optional key for idempotent requests")


class TransactionResponse(BaseModel):
    transaction_id: int
    new_balance: Decimal


class BalanceResponse(BaseModel):
    balance: Decimal
    account_id: int
    asset_type_id: int
