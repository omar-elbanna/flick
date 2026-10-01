# Deploying Flick

Flick is a two-piece app: a Next.js 14 frontend (goes on Vercel) and a FastAPI
backend with Postgres + Redis (goes on Railway). This doc walks the end-to-end
deploy from a clean machine.

## 1. Backend → Railway

Railway hosts the FastAPI container plus the Postgres and Redis the app needs.

### 1a. Create the project

1. Sign in at <https://railway.app> with the GitHub account that owns
   `omar-elbanna/flick`.
2. **New Project → Deploy from GitHub repo** → pick `omar-elbanna/flick`.
3. On the service that Railway creates, open **Settings**:
   - **Root Directory**: `backend`
   - **Build**: Dockerfile (auto-detected via `backend/railway.json`).
   - **Start Command**: leave empty — `railway.json` sets it to
     `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

### 1b. Add Postgres + Redis

In the project canvas:

1. **+ New → Database → Add PostgreSQL**. Railway sets `DATABASE_URL`.
2. **+ New → Database → Add Redis**. Railway sets `REDIS_URL`.
3. On the backend service's **Variables** tab, click **Add Reference** and
   wire these two in:
   - `DATABASE_URL` → `${{Postgres.DATABASE_URL}}` **and rewrite the scheme to
     `postgresql+asyncpg://`** (Railway's default is plain `postgresql://`,
     which the async SQLAlchemy driver rejects).
   - `REDIS_URL` → `${{Redis.REDIS_URL}}`

### 1c. Set the rest of the env

Copy the values from your local `backend/.env` into Railway's **Variables**:

```
ENVIRONMENT=production
RSA_PRIVATE_KEY=<regenerate for prod — see below>
RSA_PUBLIC_KEY=<regenerate for prod — see below>
GOOGLE_CLIENT_ID=<from .env>
GOOGLE_CLIENT_SECRET=<from .env>
GOOGLE_REDIRECT_URI=https://<backend-domain>/api/v1/auth/google/callback
TMDB_API_KEY=<from .env>
OPENAI_API_KEY=<from .env>
OPENAI_MODEL=gpt-4o-mini
FRONTEND_URL=https://<your-vercel-domain>
ALLOWED_ORIGINS=https://<your-vercel-domain>
ACCESS_TOKEN_TTL_MINUTES=15
REFRESH_TOKEN_TTL_DAYS=7
SESSION_SECRET=<regenerate for prod — openssl rand -hex 32>
JWT_ISSUER=flick
JWT_AUDIENCE=flick-clients
```

> **Regenerate RSA keys for prod** — the ones in `backend/.env` are marked
> "local dev only". From `backend/`:
> ```bash
> python scripts/generate_rsa_keys.py
> ```
> Paste both PEMs into Railway as multi-line variables (Railway supports real
> newlines; the `\n`-escaped form in `.env` also works).

### 1d. Deploy and grab the URL

1. **Settings → Networking → Generate Domain** on the backend service.
   You'll get something like `flick-backend-production.up.railway.app`.
2. Update `GOOGLE_REDIRECT_URI` in Railway to use that domain.
3. In **Google Cloud Console → Credentials → OAuth 2.0 Client**, add the
   same redirect URI to the authorized list.
4. Railway redeploys on save. Check **Deployments → Logs**: you should see
   `alembic upgrade head` run, then `Uvicorn running on …`.
5. Test: `curl https://<backend-domain>/health` → `{"status":"ok"}`.

## 2. Frontend → Vercel

1. Sign in at <https://vercel.com> with the same GitHub account.
2. **Add New → Project** → import `omar-elbanna/flick`.
3. **Configure Project**:
   - **Root Directory**: `frontend`
   - **Framework Preset**: Next.js (auto-detected)
   - Leave build / install commands at their defaults.
4. **Environment Variables**:
   ```
   NEXT_PUBLIC_API_BASE_URL=https://<backend-domain>
   NEXT_PUBLIC_WS_BASE_URL=wss://<backend-domain>
   ```
5. **Deploy**. First build takes ~2 minutes.

Once the Vercel URL is live, go back to Railway and update:
- `FRONTEND_URL=https://<vercel-domain>`
- `ALLOWED_ORIGINS=https://<vercel-domain>`

Railway redeploys. Done.

## 3. Verify end-to-end

- Open the Vercel URL. Landing page should load.
- Register a user via `/auth/register`. If sign-up succeeds, the frontend
  reached the backend reached Postgres.
- Sign in with Google. If the OAuth round-trip completes, your redirect URI
  is wired correctly.
- Start a group session, invite yourself in a second browser, see votes
  broadcast over WebSocket.

## Common gotchas

- **`asyncpg` error about `postgresql://` scheme** — rewrite `DATABASE_URL` to
  start with `postgresql+asyncpg://`.
- **CORS errors in browser console** — `ALLOWED_ORIGINS` on Railway doesn't
  include the exact Vercel URL (including protocol, no trailing slash).
- **Google OAuth `redirect_uri_mismatch`** — the URI in the Google Cloud
  Console must match `GOOGLE_REDIRECT_URI` exactly, including trailing path.
- **WebSocket won't connect** — frontend is using `ws://` on an https page;
  make sure `NEXT_PUBLIC_WS_BASE_URL` starts with `wss://`.
