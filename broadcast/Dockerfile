FROM python:3.12-slim

WORKDIR /app

# Create a non-root user for security -- if FFmpeg or Python has a vulnerability,
# an attacker does not get root inside the container.
RUN addgroup --system broadcast && adduser --system --ingroup broadcast broadcast

# Install FFmpeg for RTMP multiplexing
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R broadcast:broadcast /app

USER broadcast

EXPOSE 8100

CMD ["uvicorn", "broadcast.main:app", "--host", "0.0.0.0", "--port", "8100"]
