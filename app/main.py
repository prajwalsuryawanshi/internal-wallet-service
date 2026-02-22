from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import api_router
from app.config import settings
from app.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
