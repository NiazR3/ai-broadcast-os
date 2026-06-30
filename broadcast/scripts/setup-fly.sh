#!/usr/bin/env bash
# =============================================================================
# Broadcast OS — Fly.io Setup Script
# =============================================================================
# Run this locally after installing the Fly CLI to deploy the backend.
#
# Prerequisites:
#   1. Install Fly CLI: https://fly.io/docs/hands-on/install-flyctl/
#   2. Run: fly auth login
#   3. Have a Vercel project set up (for CORS_ORIGINS)
# =============================================================================
set -euo pipefail

log() { echo "[fly-setup] $*"; }
APP_NAME="broadcast-os"

# --- Step 1: Create the app ---
log "Creating Fly app: $APP_NAME..."
fly apps create "$APP_NAME" 2>/dev/null || log "App already exists, continuing..."

# --- Step 2: Create persistent volume ---
log "Creating persistent volume (1GB)..."
fly volumes create broadcast_data --region iad --size 1 --app "$APP_NAME" 2>/dev/null || \
  log "Volume already exists, continuing..."

# --- Step 3: Set secrets ---
log "Setting secrets..."

# Generate API key if not already set
API_KEY="${BROADCAST_API_KEY:-$(openssl rand -hex 32)}"
fly secrets set BROADCAST_API_KEY="$API_KEY" --app "$APP_NAME"

# CORS — prompt if not set
if [ -z "${BROADCAST_CORS_ORIGINS:-}" ]; then
  echo ""
  echo "Enter the CORS origin for your Vercel frontend URL"
  echo "(e.g. https://broadcast-os.vercel.app or https://app.yourdomain.com):"
  read -r CORS_ORIGIN
  fly secrets set BROADCAST_CORS_ORIGINS="$CORS_ORIGIN" --app "$APP_NAME"
  fly secrets set BROADCAST_WEBSOCKET_ALLOWED_ORIGINS="$CORS_ORIGIN" --app "$APP_NAME"
else
  fly secrets set BROADCAST_CORS_ORIGINS="$BROADCAST_CORS_ORIGINS" --app "$APP_NAME"
  fly secrets set BROADCAST_WEBSOCKET_ALLOWED_ORIGINS="$BROADCAST_CORS_ORIGINS" --app "$APP_NAME"
fi

# OBS — prompt for password
if [ -z "${BROADCAST_OBS_PASSWORD:-}" ]; then
  echo ""
  echo "Enter your OBS WebSocket server password (leave blank to skip):"
  read -rs OBS_PW
  echo ""
  if [ -n "$OBS_PW" ]; then
    fly secrets set BROADCAST_OBS_PASSWORD="$OBS_PW" --app "$APP_NAME"
  fi
else
  fly secrets set BROADCAST_OBS_PASSWORD="$BROADCAST_OBS_PASSWORD" --app "$APP_NAME"
fi

# --- Step 4: Deploy ---
log ""
log "=== Ready to deploy ==="
log "Run: fly deploy --app $APP_NAME"
log ""
log "After deploy, verify: curl https://$APP_NAME.fly.dev/health"
log ""
log "Then set your Vercel project's VITE_API_BASE to:"
echo "  https://$APP_NAME.fly.dev"
