#!/usr/bin/env bash
# =============================================================================
# Broadcast OS — VPS Setup Script (Ubuntu/Debian)
# =============================================================================
# Run this on a fresh Ubuntu 22.04+ VPS to install dependencies.
#   curl -fsSL https://raw.githubusercontent.com/NiazR3/ai-broadcast-os/main/scripts/setup-vps.sh | bash
#
# After setup:
#   1. Copy .env.production and set your secrets
#   2. docker compose -f docker-compose.prod.yml up -d
#   3. Run certbot to get SSL: docker compose exec nginx certbot --nginx
# =============================================================================

set -euo pipefail

log() { echo "[setup] $*"; }

# --- Update system ---
log "Updating system packages..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# --- Install Docker ---
if ! command -v docker &>/dev/null; then
  log "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
  log "Docker installed. You'll need to log out and back in for group changes."
else
  log "Docker already installed ($(docker --version))"
fi

# --- Install Docker Compose plugin ---
if ! docker compose version &>/dev/null; then
  log "Installing Docker Compose plugin..."
  sudo apt-get install -y -qq docker-compose-plugin
else
  log "Docker Compose already installed ($(docker compose version))"
fi

# --- Install FFmpeg (for host-level debugging) ---
if ! command -v ffmpeg &>/dev/null; then
  log "Installing FFmpeg..."
  sudo apt-get install -y -qq ffmpeg
else
  log "FFmpeg already installed ($(ffmpeg -version | head -1))"
fi

# --- Create broadcast directory ---
sudo mkdir -p /opt/broadcast/data
sudo chown -R "$USER:$(id -gn)" /opt/broadcast

log ""
log "=== Setup complete ==="
log ""
log "Next steps:"
log "  1. Clone the repo:  git clone https://github.com/NiazR3/ai-broadcast-os.git /opt/broadcast/app"
log "  2. cd /opt/broadcast/app"
log '  3. cp .env.production.example .env.production  # edit with your secrets'
log "  4. docker compose -f docker-compose.prod.yml up -d"
log "  5. Obtain SSL cert:  docker compose exec nginx certbot --nginx -d yourdomain.com"
log ""
