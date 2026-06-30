# Broadcast OS — Hybrid Deployment Guide

Deploy the AI Broadcast OS stack with the frontend on **Vercel** (free tier) and the
backend on a **Linux VPS** (starting at ~$5/mo).

```
┌───────────────┐       ┌──────────────────────┐
│  Vercel (CDN) │──────→│  VPS (Docker)        │
│               │  API  │                      │
│  React        │  calls│  nginx → FastAPI:8100 │
│  Dashboard    │       │  FFmpeg (OBS)        │
│  app.dev ◄────│←──────│  api.dev             │
└───────────────┘  CORS └──────────────────────┘
```

---

## 1. Prerequisites

| Item | Details |
|---|---|
| **GitHub repo** | `github.com/NiazR3/ai-broadcast-os` |
| **VPS** | Ubuntu 22.04+, 1 CPU / 1 GB RAM minimum, public IP |
| **Domain** | Two DNS A records pointing to your VPS IP |
| **Vercel account** | Free tier — connect your GitHub |
| **Stream keys** | Twitch / YouTube / Facebook ingest |

---

## 2. Frontend — Vercel

### 2.1 One-click deploy

1. Go to [vercel.com/new](https://vercel.com/new)
2. Import your GitHub repo (`NiazR3/ai-broadcast-os`)
3. Set **Root Directory** to `dashboard`
4. Add environment variable:
   - `VITE_API_BASE` = `https://api.yourdomain.com` (your backend domain)
5. Deploy

Vercel auto-detects Vite and runs `npm run build`. Every push to `master`
that changes `dashboard/` triggers a new deployment.

### 2.2 Custom domain

After the initial deploy, go to **Project Settings → Domains** and add
`app.yourdomain.com`. Vercel provisions a free SSL certificate automatically.

### 2.3 Manual deploy (CLI)

```bash
cd dashboard
npm ci
VITE_API_BASE=https://api.yourdomain.com npm run build
npx vercel --prod
```

---

## 3. Backend — VPS

### 3.1 Initial setup

SSH into your VPS and run:

```bash
# Install Docker + dependencies
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
# Log out and back in, then:

# Clone the repo
sudo mkdir -p /opt/broadcast/data
sudo chown "$USER:$(id -gn)" /opt/broadcast
git clone https://github.com/NiazR3/ai-broadcast-os.git /opt/broadcast/app
cd /opt/broadcast/app

# Configure environment
cp .env.production.example .env.production
# Edit .env.production with your secrets (see below)
```

### 3.2 Environment configuration

Edit `.env.production`:

```bash
# Required — generate a strong key
BROADCAST_API_KEY=$(openssl rand -hex 32)

# Allow your Vercel domain
BROADCAST_CORS_ORIGINS=https://app.yourdomain.com
BROADCAST_WEBSOCKET_ALLOWED_ORIGINS=https://app.yourdomain.com

# OBS — set password in OBS WebSocket settings first
BROADCAST_OBS_PASSWORD=your-obs-websocket-password
```

### 3.3 Start services

```bash
docker compose -f docker-compose.prod.yml up -d
```

Verify:

```bash
curl http://localhost:8100/health
# {"status":"ok","service":"ai-broadcast-os","version":"0.1.0"}
```

### 3.4 SSL (Let's Encrypt)

```bash
# Install certbot on the host
sudo apt-get install -y certbot

# Get certificate
sudo certbot certonly --standalone -d api.yourdomain.com

# Copy certs to nginx SSL directory
sudo mkdir -p /opt/broadcast/app/nginx/ssl
sudo cp /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem \
       /opt/broadcast/app/nginx/ssl/
sudo cp /etc/letsencrypt/live/api.yourdomain.com/privkey.pem \
       /opt/broadcast/app/nginx/ssl/

# Restart nginx
docker compose -f docker-compose.prod.yml restart nginx
```

> **Auto-renewal:** Add a cron job: `0 3 * * 1 certbot renew --deploy-hook "docker compose -f /opt/broadcast/app/docker-compose.prod.yml restart nginx"`

After SSL, uncomment the HTTPS server block in `nginx/nginx.conf` and update `server_name`.

---

## 4. CI/CD

The GitHub Actions workflows handle automated deployment:

### Backend (`backend.yml`)

Triggered on pushes to `master` that don't touch `dashboard/` or docs:

1. **Test** — run Python test suite
2. **Build & Push** — build Docker image → push to GHCR
3. **Deploy** — SSH into VPS, pull new image, restart service

**Secrets required** (set in GitHub repo → Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `VPS_HOST` | Your VPS IP address |
| `VPS_USER` | SSH username (e.g. `root` or `ubuntu`) |
| `VPS_SSH_KEY` | Private SSH key (deploy key) |
| `BROADCAST_API_KEY` | API key for production (same as `.env.production`) |

### Frontend (`frontend.yml`)

Triggered on pushes changing `dashboard/`:

| Secret | Value |
|---|---|
| `VERCEL_TOKEN` | Vercel account token (vercel.com → Settings → Tokens) |
| `VERCEL_ORG_ID` | Vercel org ID (vercel.com → Settings → General) |
| `VERCEL_PROJECT_ID` | Vercel project ID (from project settings) |

---

## 5. Post-deploy checklist

- [ ] `/health` returns 200 from your VPS
- [ ] SSL certificate valid (`curl https://api.yourdomain.com/health`)
- [ ] Frontend loads at `https://app.yourdomain.com`
- [ ] Dashboard talks to API (check browser console for CORS errors)
- [ ] Set stream keys in the dashboard **Platform Settings**
- [ ] OBS WebSocket connection works (backend → OBS)
- [ ] Prometheus `/metrics` accessible (if needed)
- [ ] CI/CD workflows can deploy successfully

---

## 6. Troubleshooting

| Symptom | Likely fix |
|---|---|
| Dashboard blank / CORS errors | Check `BROADCAST_CORS_ORIGINS` includes your Vercel domain exactly |
| `502 Bad Gateway` from nginx | Backend container not healthy — check `docker compose logs broadcast` |
| OBS not connecting | Ensure OBS WebSocket plugin is installed, password matches, and `BROADCAST_OBS_HOST` is correct |
| Stream not starting | Verify stream keys are set — check API: `GET /broadcast/status` |
| `stream_key` values empty | Set via dashboard or API: `POST /broadcast/config` with `{"twitch_stream_key": "live_..."}` |

---

## 7. Architecture reference

```
VPS (:80/:443)
 └── nginx (reverse proxy)
      ├── /api/*     → broadcast:8100 (FastAPI backend)
      ├── /ws/*      → broadcast:8100 (WebSocket, upgraded)
      ├── /health    → broadcast:8100
      └── /*         → /usr/share/nginx/html (static SPA)

Vercel (CDN)
 └── React SPA → calls https://api.yourdomain.com/api/*
```

The backend container stores persistent data (analytics, personas) in a Docker
volume mounted at `broadcast_data/`.
