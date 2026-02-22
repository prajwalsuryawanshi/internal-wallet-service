FROM python:3.12-slim

WORKDIR /app

# Install dependencies (no editable install needed; app code is copied below)
COPY pyproject.toml ./
RUN pip install uv && uv pip install --system fastapi "uvicorn[standard]" "sqlalchemy[asyncio]" asyncpg pydantic pydantic-settings

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
