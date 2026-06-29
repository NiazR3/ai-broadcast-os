FROM python:3.12-slim

WORKDIR /app

# Create a non-root user for security
RUN addgroup --system broadcast && adduser --system --ingroup broadcast broadcast

# Install FFmpeg for RTMP multiplexing + curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire source tree into broadcast/ package directory
# The app imports as "broadcast.main", so files need to be under broadcast/
COPY . /app/broadcast/
# Move requirements back to root (already installed, but kept for consistency)
RUN if [ -f /app/broadcast/requirements.txt ]; then \
        mv /app/broadcast/requirements.txt /app/; \
    fi

RUN chown -R broadcast:broadcast /app

ENV PYTHONPATH=/app

USER broadcast

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8100/health')" || exit 1

CMD ["uvicorn", "broadcast.main:app", "--host", "0.0.0.0", "--port", "8100"]
