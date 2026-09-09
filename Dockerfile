FROM python:3.11-slim

# Install system deps + Google Chrome (stable)
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget \
        gnupg \
        unzip \
        curl \
        fonts-liberation \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgbm1 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxkbcommon0 \
        libxrandr2 \
        xdg-utils \
    && wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y /tmp/chrome.deb \
    && rm /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/*

# Tell Selenium/webdriver-manager where Chrome lives, and force any
# HOME-relative writes (webdriver_manager cache, Chrome config) into /tmp,
# since some platforms mount the app's home directory read-only.
ENV CHROME_BIN=/usr/bin/google-chrome
ENV HOME=/tmp
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Most platforms (Render, Railway, etc.) inject a dynamic $PORT at runtime —
# default to 8000 for local/manual runs where $PORT isn't set.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD uvicorn app:app --host 0.0.0.0 --port ${PORT}
