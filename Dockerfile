FROM python:3.11-slim

# Avoid buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required for Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium binaries & system dependencies
RUN python -m playwright install --with-deps chromium

# Copy application files
COPY . /app/

# Entrypoint command to run Telegram Bot 24/7
CMD ["python", "bot.py"]
