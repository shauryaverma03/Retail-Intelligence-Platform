# Deployment

Two images — `backend` (uvicorn/FastAPI) and `frontend` (nginx serving the built
SPA and reverse-proxying `/api`) — plus a PostgreSQL 16 database. Anything that
runs containers works. All configuration is environment variables; no secret is
baked into an image.

---

## 0. Deploy to a VPS with HTTPS (recommended, ~15 min)

A `deploy/` overlay adds a **Caddy** reverse proxy (automatic Let's Encrypt HTTPS),
stops publishing Postgres / raw app ports, and flips the session cookie to
`Secure`.

**Prereqs:** a small Linux server (1–2 vCPU, 2 GB RAM, ~5 GB disk), a domain with
an `A` record pointing at the server IP, Docker + Compose installed.

```bash
# on the server
git clone <your-repo> xenopulse && cd xenopulse

cp .env.example .env
nano .env            # set the four values below

nano deploy/Caddyfile   # replace xenopulse.example.com with your domain

docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
docker compose logs -f db     # wait for "database system is ready" (seed ~1–3 min)
./scripts/smoke.sh https://your-domain/api
```

`.env` must contain:

| var | value |
|---|---|
| `POSTGRES_PASSWORD` | a strong random string |
| `SESSION_SECRET` | `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `PUBLIC_ORIGIN` | `https://your-domain` (exact, no trailing slash) |
| `ANTHROPIC_API_KEY` | optional — enables real NL→SQL |

Open `https://your-domain`. Caddy fetches a certificate on first hit. Redeploy
after a code change with the same `up -d --build` command; the `pgdata` volume is
untouched.

Ports on the host afterwards: only **80** and **443** (Caddy). Postgres, backend
and frontend are reachable only on the internal Docker network.

---

## 1. Docker Compose (single host / demo)

```bash
cp .env.example .env
# edit .env: strong POSTGRES_PASSWORD / READONLY_PASSWORD, optional ANTHROPIC_API_KEY
docker compose up -d --build
```

- First boot runs `db/init/*` (schema → seed → indexes). The partition-pruning
  demo table is opt-in: `make partition-demo` after the stack is up.
- `docker compose ps` shows health; `db` is healthy once `pg_isready` passes and
  the seed finishes.
- Needs ~3 GB free disk (images + seeded volume).
- Frontend on `FRONTEND_PORT` (default 8080), API on `BACKEND_PORT` (default
  8000).

Update after a code change: `docker compose up -d --build backend frontend`
(the DB volume `pgdata` is untouched).

---

## 2. Managed Postgres + container platform (production shape)

1. **Database:** provision managed PostgreSQL 16 (RDS / Cloud SQL / Neon / …).
   Apply the schema and seed once:

   ```bash
   psql "$ADMIN_URL" -f db/schema.sql
   psql "$ADMIN_URL" -f db/seed.sql        # or your real ETL instead of the synthetic seed
   psql "$ADMIN_URL" -f db/indexes.sql
   psql "$ADMIN_URL" -f db/partitioning.sql   # optional
   ```

   `db/schema.sql` creates the `xeno_readonly` login role. Rotate its password
   and pass it via `DATABASE_URL_RO`.

2. **Backend image:**

   ```bash
   docker build -f backend/Dockerfile -t <registry>/xenopulse-backend:<tag> .
   ```

   Required env:

   | var | example |
   |---|---|
   | `DATABASE_URL` | `postgresql://app_user:***@db.internal:5432/xenopulse` |
   | `DATABASE_URL_RO` | `postgresql://xeno_readonly:***@db.internal:5432/xenopulse` |
   | `CORS_ORIGINS` | `https://analytics.example.com` |
   | `ANTHROPIC_API_KEY` | *(optional)* |
   | `AI_MODEL` | `claude-sonnet-5` |
   | `QUERY_ROW_LIMIT` / `STATEMENT_TIMEOUT_MS` | `1000` / `8000` |

   Health/readiness probes: `GET /api/health` (liveness), `GET /api/ready`
   (readiness — checks DB + seed). Run more than one replica behind a load
   balancer; the only in-process state is a 60s dashboard cache.

3. **Frontend image:**

   ```bash
   docker build -f frontend/Dockerfile -t <registry>/xenopulse-frontend:<tag> ./frontend
   ```

   The build inlines `VITE_API_BASE=/api`. `frontend/nginx.conf` proxies
   `location /api/` to `http://backend:8000/api/` — change that upstream to your
   backend service's address, or drop the proxy block and point `VITE_API_BASE`
   at the backend's public URL at build time.

---

## 3. Configuration reference

| var | default | notes |
|---|---|---|
| `DATABASE_URL` | `postgresql://xeno:xeno@db:5432/xenopulse` | owner / trusted connection |
| `DATABASE_URL_RO` | `postgresql://xeno_readonly:xeno_readonly_pw@db:5432/xenopulse` | least-privilege connection for user & AI SQL |
| `ANTHROPIC_API_KEY` | *(empty)* | empty ⇒ rule-based NL→SQL fallback |
| `AI_MODEL` | `claude-sonnet-5` | any Anthropic model id |
| `AI_MAX_TOKENS` | `1500` | per LLM call |
| `QUERY_ROW_LIMIT` | `1000` | hard cap wrapped around every user/AI query |
| `STATEMENT_TIMEOUT_MS` | `8000` | `SET LOCAL statement_timeout` for read-only execution |
| `EXPLAIN_TIMEOUT_MS` | `30000` | timeout for `EXPLAIN ANALYZE` |
| `DASHBOARD_CACHE_TTL_S` | `60` | in-process dashboard cache |
| `CORS_ORIGINS` | `http://localhost:5173` | comma-separated allowed origins |

---

## 4. Operational notes

- **Least privilege:** confirm `xeno_readonly` holds only `CONNECT` + `USAGE` +
  `SELECT`. `db/schema.sql` also pins `default_transaction_read_only = on` and a
  `statement_timeout` on the role itself.
- **Performance Lab runs DDL** (`CREATE`/`DROP INDEX` on `campaign_events` and
  `orders`) on the owner connection, serialised by a process lock, and restores
  the production indexes afterward. If you don't want that in a given
  environment, don't expose `/api/performance/*` (or run the app with a
  reverse-proxy rule blocking it).
- **Backups:** only `pgdata` matters. The app is stateless.
- **Scaling:** backend is horizontally scalable; increase pool sizes in
  `backend/app/db.py` (`app_pool` / `ro_pool`) if you add replicas under load.
- **Re-seed / refresh synthetic data:**
  `docker compose exec -T db psql -U xeno -d xenopulse < db/seed.sql`.
