# Broadcast OS — Hybrid Deployment Guide (Fly.io + Vercel)

Deploy the AI Broadcast OS stack with the **backend on Fly.io** (free $5/mo credit)
and the **frontend on Vercel** (free tier).

```
Vercel (CDN)                  Fly.io (global)
  ┌─────────────┐             ┌───────────────┐
  │ React       │  API calls  │ broadcast-os  │
  │ Dashboard   │──────────→  │ FastAPI:8100  │
  │ app.dev ◄───│←── CORS ──│  FFmpeg/OBS   │
  └─────────────┘   HTTPS     │ Volume: data  │
                              └───────────────┘
```

---

## 1. Prerequisites

| Item | Details |
|---|---|
| **GitHub repo** | `github.com/NiazR3/ai-broadcast-os` |
| **Fly.io account** | [fly.io/signup](https://fly.io/signup) — card required for ID verify, **never charged on free tier** |
| **Vercel account** | [vercel.com/signup](https://vercel.com/signup) — connect GitHub |
| **Domain** (optional) | A custom domain for production |

---

## 2. Backend — Fly.io

### 2.1 Install Fly CLI

```bash
# Windows (PowerShell)
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"

# macOS/Linux
curl -fsSL https://fly.io/install.sh | sh
```

### 2.2 Launch the app

```bash
# Log in
fly auth login

# Create the app (one time only)
cd broadcast
fly launch --ha=false --no-deploy

# Set app name to match fly.toml
fly apps create broadcast-os
```

### 2.3 Create persistent volume

```bash
fly volumes create broadcast_data --region iad --size 1
```

### 2.4 Set secrets

```bash
# Generate and set the API key
fly secrets set BROADCAST_API_KEY=$(openssl rand -hex 32)

# Allow your Vercel domain
fly secrets set BROADCAST_CORS_ORIGINS=https://app.yourdomain.com
fly secrets set BROADCAST_WEBSOCKET_ALLOWED_ORIGINS=https://app.yourdomain.com

# OBS WebSocket (set password in OBS first)
fly secrets set BROADCAST_OBS_PASSWORD=your-obs-password

# Stream keys (can also be set via dashboard after deploy)
fly secrets set BROADCAST_TWITCH_STREAM_KEY=
fly secrets set BROADCAST_YOUTUBE_STREAM_KEY=
fly secrets set BROADCAST_FACEBOOK_STREAM_KEY=
```

### 2.5 Deploy

```bash
fly deploy
```

Wait for it to finish, then verify:

```bash
curl https://broadcast-os.fly.dev/health
# {"status":"ok","service":"ai-broadcast-os","version":"0.1.0"}
```

Fly.io issues a free `*.fly.dev` subdomain with auto-SSL. You can add a custom
domain later: `fly certs create api.yourdomain.com`

---

## 3. Frontend — Vercel

### 3.1 Deploy

1. Go to [vercel.com/new](https://vercel.com/new)
2. **Import** your GitHub repo (`NiazR3/ai-broadcast-os`)
3. **Root Directory** — set to `dashboard`
4. Framework auto-detects Vite
5. **Environment Variables**:
   - `VITE_API_BASE` = `https://broadcast-os.fly.dev` (your Fly.io app URL)
6. **Deploy**

### 3.2 Custom domain (optional)

Project Settings → Domains → add `app.yourdomain.com`

---

## 4. CI/CD

### Backend (`backend.yml`)

On push to `master` (excluding dashboard/docs):
1. **Test** — Python test suite
2. **Deploy** — `flyctl deploy` to Fly.io

**Required secret** (repo → Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `FLY_API_TOKEN` | From Fly.io: `fly tokens create deploy` |
| `BROADCAST_API_KEY` | Same as set on Fly |
| `BROADCAST_CORS_ORIGINS` | e.g. `https://app.yourdomain.com` |
| `BROADCAST_WEBSOCKET_ALLOWED_ORIGINS` | Same as CORS |
| `BROADCAST_OBS_PASSWORD` | OBS WebSocket password |

### Frontend (`frontend.yml`)

On push changing `dashboard/`:
1. **Lint**
2. **Deploy to Vercel**

**Required secrets:**

| Secret | Value |
|---|---|
| `VERCEL_TOKEN` | Vercel → Settings → Tokens → Create |
| `VERCEL_ORG_ID` | Vercel → Settings → General → Team ID |
| `VERCEL_PROJECT_ID` | From your Vercel project → Settings → Project ID |

---

## 5. Post-deploy checklist

- [ ] `curl https://broadcast-os.fly.dev/health` returns 200
- [ ] Frontend loads at `https://<vercel-app>.vercel.app`
- [ ] Dashboard shows connected to API (no CORS errors in console)
- [ ] Prometheus `/metrics` accessible
- [ ] CI/CD can deploy (trigger a push or manual workflow run)

---

## 6. Free tier limits

| Resource | Fly.io Free Allowance | Broadcast OS Usage |
|---|---|---|
| **RAM** | 256 MB per shared VM (3 VMs) | ~150-200 MB (FastAPI + FFmpeg) |
| **CPU** | Shared, up to 1 vCPU burst | Light ~5-10% idle |
| **Storage** | 3 GB persistent volume | SQLite DB + logs (<100 MB) |
| **Bandwidth** | 160 GB outbound / mo | RTMP streaming outbound |
| **SSL** | Automatic | Included |

> **If you need more RAM for high-bitrate streaming:** resize the machine with
> `fly machine update <id> --memory 1024` (~$6/mo).

---

## 7. Troubleshooting

| Symptom | Likely fix |
|---|---|
| Dashboard blank / CORS errors | Make sure `VITE_API_BASE` in Vercel matches your Fly.io app URL exactly |
| `curl /health` fails | Run `fly logs` to check startup errors |
| OBS not connecting | Ensure OBS WebSocket plugin is installed and password matches `BROADCAST_OBS_PASSWORD` |
| Stream not starting | Set stream keys via dashboard or `fly secrets set BROADCAST_TWITCH_STREAM_KEY=...` |
| Volume not mounting | Run `fly volumes list` to verify volume exists; re-create if missing |

---

## 8. Local development with Fly

```bash
# Test the Docker build locally
docker build -t broadcast-os .

# Run with environment file
docker run --rm -p 8100:8100 --env-file .env broadcast-os

# Or use the dev compose file
docker compose up
```
