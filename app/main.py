import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fastapi import Depends

from app.api.routes import api_router
from app.config import settings
from app.database import engine, Base, get_db
from app.seed import run_seed

logger = logging.getLogger(__name__)


async def _init_db():
    """Retry DB connection and create tables. Runs in background so app can bind to PORT."""
    for attempt in range(30):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initialized successfully")
            return
        except Exception as e:
            wait = min(2**attempt, 30)
            logger.warning("DB init failed (attempt %d/30), retrying in %ds: %s", attempt + 1, wait, e)
            await asyncio.sleep(wait)
    logger.error("Database initialization failed after 30 attempts")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Don't block startup on DB - Render needs port bound quickly. Init DB in background.
    asyncio.create_task(_init_db())
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="Internal wallet service for credits/points. Closed-loop, double-entry ledger.",
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api/v1")


@app.post("/seed", summary="Seed database")
async def seed_db(db=Depends(get_db)):
    """Seed asset types, accounts, and initial balances. Idempotent."""
    msg = await run_seed(db)
    return {"status": "ok", "message": msg}


@app.get("/health")
def health():
    return {"status": "ok"}
