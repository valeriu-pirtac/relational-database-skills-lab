import asyncio

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import MissingGreenlet
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_async_session, get_leaked_session, query_counter
from app.models import BankAccount
from app.schemas import BankAccountWithUserSchema, TransferRequest, TransferResponse


app = FastAPI(
    title="SQLAlchemy Async Session Management Lab API",
    description="Exposes endpoints demonstrating correct scoped sessions, leaked global sessions under concurrent load, and lazy-loading greenlet errors.",
)


@app.exception_handler(MissingGreenlet)
async def missing_greenlet_exception_handler(request, exc: MissingGreenlet):
    """
    Catch standard MissingGreenlet exception and return a highly detailed 500 error,
    explaining why this failure happens in FastAPI async session serialization.
    """
    error_detail = (
        "SQLAlchemy MissingGreenlet Error! You attempted to access an unloaded "
        "lazy-loaded relationship during Pydantic serialization outside of an active database context. "
        "Under an async session, relationship lazy-loading is physically impossible because "
        "the serialization process runs synchronously and cannot await database requests. "
        "Fix this by using eager loading: joinedload() or selectinload()."
    )
    logger.error(f"[FastAPI Failure] MissingGreenlet raised: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error_type": "MissingGreenlet", "message": error_detail, "original_exception": str(exc)},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Catch any other exception (like PendingRollbackError, InvalidRequestError) and log it."""
    exc_type = type(exc).__name__
    logger.error(f"[FastAPI Failure] Exception raised: {exc_type}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error_type": exc_type, "message": str(exc)},
    )


@app.get("/lazy-load-error", response_model=BankAccountWithUserSchema)
async def get_account_lazy(db: AsyncSession = Depends(get_async_session)):  # noqa: B008
    """
    Intentionally bad endpoint: fetches a bank account without any eager loading.
    Accessing the 'user' relationship during Pydantic serialization will trigger a MissingGreenlet exception.
    """
    query_counter.reset()
    query_counter.enable_logging(True)
    logger.info("[FastAPI Request] /lazy-load-error called. Querying bank account without eager loading...")

    # Fetch bank account without eager loading
    result = await db.execute(select(BankAccount).limit(1))
    account = result.scalars().first()

    if not account:
        raise HTTPException(status_code=404, detail="No accounts found. Make sure to run bootstrap first.")

    logger.info("[FastAPI] Account retrieved. Returning to serialize...")
    # Returning this directly will trigger serialization and raise MissingGreenlet
    return account


@app.get("/lazy-load-fixed", response_model=BankAccountWithUserSchema)
async def get_account_fixed(db: AsyncSession = Depends(get_async_session)):  # noqa: B008
    """
    Correct endpoint: fetches a bank account with selectinload eager loading.
    """
    query_counter.reset()
    query_counter.enable_logging(True)
    logger.info("[FastAPI Request] /lazy-load-fixed called. Querying bank account with selectinload...")

    # Fetch bank account with eager loading
    result = await db.execute(select(BankAccount).options(selectinload(BankAccount.user)).limit(1))
    account = result.scalars().first()

    if not account:
        raise HTTPException(status_code=404, detail="No accounts found. Make sure to run bootstrap first.")

    logger.info("[FastAPI] Account retrieved with selectinload. Serializing...")
    return account


@app.post("/transfer/safe", response_model=TransferResponse)
async def transfer_funds_safe(payload: TransferRequest, db: AsyncSession = Depends(get_async_session)):  # noqa: B008
    """
    SAFE: Performs account balance transfer using a properly scoped request session.
    Even with overlapping concurrent requests, each request gets its own session and connection.
    """
    query_counter.reset()
    query_counter.enable_logging(True)
    logger.info(
        f"[Safe Transfer] Request to transfer {payload.amount} from {payload.from_account} to {payload.to_account}"
    )

    # Start a clean isolated transaction
    async with db.begin():
        # Fetch from account
        from_stmt = select(BankAccount).where(BankAccount.account_number == payload.from_account).with_for_update()
        from_result = await db.execute(from_stmt)
        from_acc = from_result.scalars().first()

        # Fetch to account
        to_stmt = select(BankAccount).where(BankAccount.account_number == payload.to_account).with_for_update()
        to_result = await db.execute(to_stmt)
        to_acc = to_result.scalars().first()

        if not from_acc or not to_acc:
            raise HTTPException(status_code=400, detail="One or both accounts do not exist.")

        if from_acc.balance < payload.amount:
            raise HTTPException(status_code=400, detail="Insufficient funds.")

        # Simulate network or processing latency to amplify potential race conditions
        # (With safe sessions, this is perfectly isolated!)
        await asyncio.sleep(0.1)

        # Apply transfer
        from_acc.balance -= payload.amount  # type: ignore
        to_acc.balance += payload.amount  # type: ignore

        # Flush changes
        await db.flush()

        logger.success(
            f"[Safe Transfer] Transfer completed: from_balance={from_acc.balance}, to_balance={to_acc.balance}"
        )

        return TransferResponse(
            status="success",
            message="Transfer completed successfully.",
            amount=payload.amount,
            from_balance=from_acc.balance,  # type: ignore
            to_balance=to_acc.balance,  # type: ignore
        )


@app.post("/transfer/leaked", response_model=TransferResponse)
async def transfer_funds_leaked(payload: TransferRequest, db: AsyncSession = Depends(get_leaked_session)):  # noqa: B008
    """
    LEAKED: Performs account balance transfer using a globally shared singleton session.
    Under concurrent requests, this will corrupt transaction state, mix queries,
    and trigger PendingRollbackError / InvalidRequestError or session lockouts.
    """
    query_counter.reset()
    query_counter.enable_logging(True)
    logger.warning(
        f"[Leaked Transfer] Request using SHARED session: {payload.amount} from {payload.from_account} to {payload.to_account}"
    )

    # We do NOT use "async with db.begin()" inside the handler because multiple requests would overlap
    # and call begin() on an already-started transaction, throwing errors immediately!
    # Instead, we just execute on the shared session.

    # 1. Fetch from account
    from_stmt = select(BankAccount).where(BankAccount.account_number == payload.from_account)
    from_result = await db.execute(from_stmt)
    from_acc = from_result.scalars().first()

    # 2. Fetch to account
    to_stmt = select(BankAccount).where(BankAccount.account_number == payload.to_account)
    to_result = await db.execute(to_stmt)
    to_acc = to_result.scalars().first()

    if not from_acc or not to_acc:
        raise HTTPException(status_code=400, detail="One or both accounts do not exist.")

    if from_acc.balance < payload.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds.")

    # Artificial delay to ensure overlap between concurrent requests
    await asyncio.sleep(0.2)

    # 3. Apply transfer
    from_acc.balance -= payload.amount  # type: ignore
    to_acc.balance += payload.amount  # type: ignore

    # Commit the shared session
    await db.commit()

    logger.success(
        f"[Leaked Transfer] Transaction committed. from_balance={from_acc.balance}, to_balance={to_acc.balance}"
    )

    return TransferResponse(
        status="success",
        message="Leaked transfer completed successfully (may contain silent balance corruption).",
        amount=payload.amount,
        from_balance=from_acc.balance,  # type: ignore
        to_balance=to_acc.balance,  # type: ignore
    )
