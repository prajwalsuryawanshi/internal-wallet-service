import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.api.routes import api_router
from app.config import settings
from app.database import engine, Base

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Retry DB connection (Render DB may not be ready when web service starts)
    for attempt in range(10):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            break
        except Exception as e:
            if attempt < 9:
                wait = 2**attempt
                logger.warning("DB connection failed (attempt %d/10), retrying in %ds: %s", attempt + 1, wait, e)
                await asyncio.sleep(wait)
            else:
                raise
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="Internal wallet service for credits/points. Closed-loop, double-entry ledger.",
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
