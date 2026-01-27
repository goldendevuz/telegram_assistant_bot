FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Minimal deps
RUN pip install --no-cache-dir --upgrade pip

# Install runtime deps
RUN pip install --no-cache-dir telethon python-dotenv

# App
COPY . /app

# Default command
CMD ["python", "main.py"]
