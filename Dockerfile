FROM python:3.12-slim

WORKDIR /app

# Install dependencies (no editable install needed; app code is copied below)
COPY pyproject.toml ./
RUN pip install uv && uv pip install --system \
    fastapi \
    "uvicorn[standard]" \
    "sqlalchemy[asyncio]" \
    asyncpg \
    aiosqlite \
    pydantic \
    pydantic-settings

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV PORT=8000
# Render sets PORT at runtime; use shell so $PORT is expanded
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
