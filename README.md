# Flick

Group movie nights, decided. Friends join a real-time session, their individual taste
profiles are blended into a group taste vector, and an LLM surfaces 5 consensus picks
that everyone votes on yes / no / maybe. The winner appears on every screen at once.

---

## Architecture

```
┌──────────────┐         ┌──────────────────────────────────┐         ┌──────────────┐
│  Next.js 14  │  HTTPS  │   FastAPI (Python 3.12, async)   │  ─────► │  PostgreSQL  │
│  App Router  │ ◄─────► │   • RS256 JWT + refresh rotate   │         │      16      │
│  Tailwind    │   WS    │   • Group session orchestrator   │         └──────────────┘
│  shadcn/ui   │ ◄─────► │   • WebSocket broadcast manager  │  ─────► ┌──────────────┐
│  TanStack Q  │         │   • slowapi rate limiting        │         │   Redis 7    │
│  Zustand     │         │   • bleach input sanitization    │         └──────────────┘
└──────────────┘         └──────────────────────────────────┘
                                     │
                                     │ httpx + tenacity (retry, cache)
                                     ▼
                         ┌────────────────────────┐
                         │  TMDB v3  · OpenAI v1  │  (server-side only — keys never
                         │  (gpt-4o-mini)         │   reach the frontend)
                         └────────────────────────┘
```

## What's inside

- **Backend** — FastAPI + SQLAlchemy 2.0 async, Alembic migrations, structlog JSON logs,
  Pydantic v2 strict schemas, slowapi + Redis rate limiting, bandit security scanning.
- **Frontend** — Next.js 14 App Router, TypeScript strict, Tailwind, shadcn/ui primitives,
  TanStack Query, Zustand for in-memory auth (no localStorage tokens), authenticated
  WebSocket with exponential-backoff reconnect.
- **Real-time group sessions** — see `app/services/group_service.py` for the full
  orchestration: rating-count validation, taste vector aggregation, OpenAI prompt,
  candidate broadcast, vote tally, weighted-score winner selection, 5-minute timeout.

## Security checklist (all enforced)

| # | Item | Where |
|---|---|---|
| 1 | RS256 asymmetric JWTs, 15-min access, 7-day refresh | `app/utils/jwt_utils.py` |
| 2 | Refresh token rotation + family theft detection | `verify_and_rotate_refresh_token` |
| 3 | bcrypt(12) password hashing | `app/services/auth_service.py` |
| 4 | slowapi + Redis: 100/min general, 5/min auth, 10/min AI | `app/utils/rate_limit.py` + decorators |
| 5 | Strict CORS allowlist (no `*`) | `app/main.py` |
| 6 | Pydantic v2 `strict=True, extra='forbid'` everywhere | all `app/schemas/*` |
| 7 | All env vars validated on startup; app refuses to boot without them | `app/config.py` |
| 8 | TMDB + OpenAI keys server-side only | `app/utils/{tmdb,openai}_client.py` |
| 9 | CSP, HSTS, XFO, nosniff, Referrer-Policy, Permissions-Policy | `app/middleware/security_headers.py` |
| 10 | HTTPS redirect in production | `app/middleware/https_redirect.py` |
| 11 | Refresh token in httpOnly + Secure + SameSite=Strict cookie | `app/routers/auth.py` |
| 12 | Google OAuth 2.0 with PKCE (S256) + state validation | `auth_service.generate_pkce_pair` |
| 13 | SQLAlchemy ORM exclusively, no raw SQL | all services |
| 14 | bleach HTML sanitization on user text | `app/utils/sanitize.py` |
| 15 | WebSocket JWT auth on upgrade | `app/routers/websocket.py::_authenticate` |
| 16 | structlog JSON; failed logins, token theft, rate hits all logged (never PII) | `app/utils/logging.py` |
| 17 | Dependabot weekly for pip, npm, GitHub Actions, Docker | `.github/dependabot.yml` |
| 18 | `bandit -r app -ll` in CI; fails the build on HIGH | `.github/workflows/ci.yml` |

## Local development

```bash
# 1. Generate the RSA key pair for JWT signing
cd backend
python scripts/generate_rsa_keys.py   # paste output into backend/.env

# 2. Configure environment
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# Fill in TMDB_API_KEY, OPENAI_API_KEY, GOOGLE_CLIENT_ID / SECRET

# 3. Bring up the stack
docker compose up --build

# 4. Run migrations (first time only)
docker compose exec backend alembic upgrade head
```

Then open <http://localhost:3000>.

## Environment variables (backend)

| Variable | Required | Notes |
|---|---|---|
| `ENVIRONMENT` | yes | `development` / `production` / `test` |
| `DATABASE_URL` | yes | `postgresql+asyncpg://…` |
| `REDIS_URL` | yes | `redis://host:6379/0` |
| `RSA_PRIVATE_KEY` | yes | PEM-encoded RSA-2048, generated via `scripts/generate_rsa_keys.py` |
| `RSA_PUBLIC_KEY` | yes | matching public PEM |
| `GOOGLE_CLIENT_ID` | yes | Google OAuth client id |
| `GOOGLE_CLIENT_SECRET` | yes | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | no | defaults to `http://localhost:8000/api/v1/auth/google/callback` |
| `TMDB_API_KEY` | yes | TMDB v3 API key (server-side only) |
| `OPENAI_API_KEY` | yes | OpenAI key (server-side only) |
| `OPENAI_MODEL` | no | default `gpt-4o-mini` |
| `FRONTEND_URL` | yes | used for OAuth final redirect |
| `ALLOWED_ORIGINS` | yes | comma-separated CORS allowlist |
| `ACCESS_TOKEN_TTL_MINUTES` | no | default 15 |
| `REFRESH_TOKEN_TTL_DAYS` | no | default 7 |
| `SESSION_SECRET` | yes | random 16+ chars |

## API surface (versioned at `/api/v1`)

- **Auth**: `POST /auth/{register,login,refresh,logout}`, `GET /auth/{me,google,google/callback}`
- **Movies**: `GET /movies/{search,trending,genres,{tmdb_id}}`
- **Ratings**: `POST /ratings`, `DELETE /ratings/{id}`, `GET /users/me/ratings`
- **Watchlist**: `POST /watchlist`, `PATCH /watchlist/{id}`, `DELETE /watchlist/{id}`, `GET /users/me/watchlist`
- **Recommendations**: `POST /recommendations/{personal,mood}`, `GET /recommendations/similar/{tmdb_id}`
- **Groups**: `POST /groups`, `GET /groups`, `GET /groups/{id}`, `POST /groups/join`, `DELETE /groups/{id}/members/me`, `GET /groups/{id}/members`
- **Sessions**: `POST /groups/{id}/sessions`, `GET /groups/{id}/sessions/{sid}`, `POST /groups/{id}/sessions/{sid}/votes`
- **WebSocket**: `WS /ws/sessions/{sid}?token=<jwt>` — JWT validated on upgrade

Errors follow `{"detail": "human", "code": "MACHINE_CODE"}`.

## Tests

```bash
cd backend && pytest -q
```

`tests/conftest.py` builds an isolated in-memory SQLite database, stubs TMDB/OpenAI/Redis,
and provides an `auth_token` fixture. Coverage: auth (incl. token theft detection),
movies, ratings, groups.

## Deployment

- **Backend** → Railway (`.github/workflows/deploy.yml` runs `railway up`)
- **Frontend** → Vercel (same workflow runs `vercel deploy --prod`)

Set `RAILWAY_TOKEN` and `VERCEL_TOKEN` as repository secrets.

## File map

```
flick/
├── backend/
│   ├── app/
│   │   ├── main.py · config.py · database.py · dependencies.py
│   │   ├── models/        SQLAlchemy 2.0 ORM models
│   │   ├── schemas/       Pydantic v2 strict schemas
│   │   ├── routers/       FastAPI APIRouters
│   │   ├── services/      auth / movie / recommendation / group / taste_profile
│   │   ├── middleware/    security_headers + https_redirect
│   │   └── utils/         jwt / tmdb_client / openai_client / redis_client / sanitize / rate_limit / logging
│   ├── alembic/           migrations (initial schema in versions/0001_…)
│   ├── tests/             conftest + per-router tests
│   └── scripts/           generate_rsa_keys.py
├── frontend/
│   └── src/
│       ├── app/           App Router pages (home, auth, movies, profile, groups, session)
│       ├── components/    nav, movie-card, mood-search, vote-card, group-session, ui/*
│       ├── hooks/         use-auth, use-movies, use-group, use-websocket
│       ├── lib/           api (axios+interceptor), auth, cn
│       ├── store/         auth-store, session-store (Zustand)
│       └── types/         single source of truth mirroring backend schemas
├── docker-compose.yml · docker-compose.prod.yml
└── .github/               workflows + dependabot
```
