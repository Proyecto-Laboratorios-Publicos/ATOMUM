# ---------- Build stage ----------
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN pip install --upgrade pip && \
    pip install poetry

COPY pyproject.toml ./
RUN poetry install --only main --no-root --no-interaction --no-ansi

COPY . .

# ---------- Runtime stage ----------
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ATOMUM_ENV=production

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

EXPOSE 8000 8001 8002 8003

CMD ["uvicorn", "atomum.inference.api:app", "--host", "0.0.0.0", "--port", "8001"]
