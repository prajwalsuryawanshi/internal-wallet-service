from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import account_repo
from app.schemas import BalanceResponse, TransactionRequest, TransactionResponse
from app.services.wallet import wallet_service
from app.services.wallet import InsufficientBalanceError

router = APIRouter()


@router.get(
    "/users/{external_user_id}/balance",
    response_model=BalanceResponse,
    summary="Get balance",
    description="Get user balance for an asset type by external user id and asset_type_id.",
)
async def get_balance(
    external_user_id: str = Path(..., description="External user identifier"),
    asset_type_id: int = Query(..., description="Asset type id"),
    db: AsyncSession = Depends(get_db),
):
    account = await account_repo.get_user_by_external_id(db, external_user_id)
    if not account:
        raise HTTPException(status_code=404, detail="User account not found")
    balance = await wallet_service.get_balance(db, account.id, asset_type_id)
    return BalanceResponse(
        balance=balance,
        account_id=account.id,
        asset_type_id=asset_type_id,
    )


@router.post(
    "/users/{external_user_id}/top-up",
    response_model=TransactionResponse,
    summary="Wallet top-up (purchase)",
    description="Credit user wallet (e.g. after real-money purchase). Idempotent when idempotency_key is sent.",
)
async def top_up(
    external_user_id: str = Path(..., description="External user identifier"),
    body: TransactionRequest = ...,
    db: AsyncSession = Depends(get_db),
):
    account = await account_repo.get_user_by_external_id(db, external_user_id)
    if not account:
        raise HTTPException(status_code=404, detail="User account not found")
    try:
        tx_id, new_balance = await wallet_service.top_up(
            db,
            account.id,
            body.asset_type_id,
            body.amount,
            body.idempotency_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TransactionResponse(transaction_id=tx_id, new_balance=new_balance)


@router.post(
    "/users/{external_user_id}/bonus",
    response_model=TransactionResponse,
    summary="Bonus / incentive",
    description="Issue free credits to user (e.g. referral). Idempotent with idempotency_key.",
)
async def bonus(
    external_user_id: str = Path(..., description="External user identifier"),
    body: TransactionRequest = ...,
    db: AsyncSession = Depends(get_db),
):
    account = await account_repo.get_user_by_external_id(db, external_user_id)
    if not account:
        raise HTTPException(status_code=404, detail="User account not found")
    try:
        tx_id, new_balance = await wallet_service.bonus(
            db,
            account.id,
            body.asset_type_id,
            body.amount,
            body.idempotency_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TransactionResponse(transaction_id=tx_id, new_balance=new_balance)


@router.post(
    "/users/{external_user_id}/spend",
    response_model=TransactionResponse,
    summary="Spend credits",
    description="Debit user wallet (e.g. in-app purchase). Fails if balance insufficient. Idempotent with idempotency_key.",
)
async def spend(
    external_user_id: str = Path(..., description="External user identifier"),
    body: TransactionRequest = ...,
    db: AsyncSession = Depends(get_db),
):
    account = await account_repo.get_user_by_external_id(db, external_user_id)
    if not account:
        raise HTTPException(status_code=404, detail="User account not found")
    try:
        tx_id, new_balance = await wallet_service.spend(
            db,
            account.id,
            body.asset_type_id,
            body.amount,
            body.idempotency_key,
        )
    except InsufficientBalanceError as e:
        raise HTTPException(status_code=402, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TransactionResponse(transaction_id=tx_id, new_balance=new_balance)
