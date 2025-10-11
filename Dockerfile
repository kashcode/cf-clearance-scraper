###########
# BUILDER #
###########
FROM python:3.12-slim-bookworm AS builder

WORKDIR /usr/src/app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install pip tools (no system deps here, just build Python wheels)
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /usr/src/app/wheels -r requirements.txt


#########
# FINAL #
#########
FROM python:3.12-slim-bookworm

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CHROME_BIN=/usr/bin/chromium

# --- Install Chromium and minimal runtime libs ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    fonts-liberation \
    wget \
    && rm -rf /var/lib/apt/lists/*

# --- Install Python dependencies from builder ---
COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install --no-cache-dir /wheels/*

# --- Copy your app ---
COPY . /app

# --- Prepare user and permissions (so Chromium runs without --no-sandbox) ---
RUN useradd -m app && \
    mkdir -p /app/.cache/jnrbsn-user-agents && \
    chown -R app:app /app
USER app

# --- Expose and run Quart ---
EXPOSE 8080
CMD ["hypercorn", "--bind", "0.0.0.0:8080", "app:app"]
