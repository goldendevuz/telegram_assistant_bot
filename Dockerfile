FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /bin/uv

# Root bo'lmagan foydalanuvchi; session saqlanadigan papka unga tegishli
RUN groupadd -r app && useradd -r -u 1000 -g app -d /app app && \
    mkdir -p /app/data && chown app:app /app/data

WORKDIR /app

# Bog'liqliklar uv.lock bo'yicha aniq versiyalarda o'rnatiladi
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=app:app . .

USER app

# Bot heartbeat faylini yangilab turadi; fayl 3 daqiqadan eski bo'lsa unhealthy
HEALTHCHECK --interval=60s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import os, sys, time; sys.exit(0 if time.time() - os.path.getmtime('/tmp/bot_heartbeat') < 180 else 1)"

CMD ["python", "main.py"]
