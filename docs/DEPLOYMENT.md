# Deployment

Three containers — database, API, web — and one command to start them. This document
covers the local containerised run, the settings a real deployment has to supply, what
to do on the managed platforms, and the handful of operational facts worth knowing
before something goes wrong.

---

## 1. Run the whole stack locally

The commands are in the [README's Quick Start](../README.md#option-a--docker-the-whole-stack)
and are not repeated here. Two things about them are worth knowing:

Compose **refuses to start** without `POSTGRES_PASSWORD` and `SECRET_KEY` rather than
falling back to a default. A database whose password came from a committed file does not
have a password, and a signing key that ships in the repository signs tokens anybody can
forge.

### What each container is

| Service | Image | Exposed | Purpose |
| :-- | :-- | :-- | :-- |
| `db` | `postgres:16-alpine` | no | Data. A named volume survives `docker compose down`. |
| `api` | built from `backend/` | no | FastAPI under uvicorn, one worker. |
| `web` | built from `frontend/` | `8080` | nginx: serves the built bundle, proxies `/api` to `api`. |

Only `web` is published. The API is reached through nginx, so there is one way in, and
Postgres is not reachable from the host at all — an exposed development database is
the most common way a stack like this becomes an incident.

### Why the frontend needs no API URL

`services/api.js` uses `baseURL: ''`, so the browser calls `/api/...` on whatever
origin served the page, and nginx forwards it. There is no `VITE_API_URL` to set
per environment and get wrong, and no cross-origin request to permit.

---

## 2. Settings

Everything is read from the environment. `backend/.env.example` documents the same
list for a non-containerised run.

| Variable | Default | Notes |
| :-- | :-- | :-- |
| `DATABASE_URL` | local Postgres | `postgres://` and `postgresql://` are both rewritten to `postgresql+psycopg://`, so a URL copied from a managed provider works as given. |
| `SECRET_KEY` | dev value | **Required in production.** Startup fails on the development value or on anything under 32 characters. |
| `ENVIRONMENT` | `development` | `production` turns on the check above. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | |
| `CORS_ORIGINS` | localhost dev ports | Comma-separated. Not a JSON list — a list-typed setting would make pydantic demand JSON, which no dashboard emits. |
| `LOG_LEVEL` | `INFO` | |
| `LOG_JSON` | `false` | `true` emits one JSON object per line for a log collector. |
| `DB_CONNECT_ATTEMPTS` | `10` | Startup waits for the database instead of crash-looping. |
| `DB_CONNECT_BACKOFF_SECONDS` | `1.5` | |
| `DB_CONNECT_TIMEOUT_SECONDS` | `10` | Without a bound, an unreachable host is not an error but a twenty-second hang per address family. |
| `OPS_CONSUMER_KEY` / `_SECRET` | empty | Optional. The patent modules read the seeded cache and only need these to add an uncached technology. |

---

## 3. Health probes

| Endpoint | Checks | Use for |
| :-- | :-- | :-- |
| `GET /health` | that the process is answering | **liveness** |
| `GET /health/ready` | liveness **plus** a database round-trip | **readiness** |

The split matters. A liveness probe that fails on a database blip gets the container
killed and restarted, which cannot repair a database and drops every in-flight request
to achieve nothing. A readiness failure takes the instance out of the load balancer,
which is the correct response — so `/health/ready` returns **503** with a reason.

Point your orchestrator's liveness probe at `/health` and its readiness probe at
`/health/ready`. Never the other way round.

---

## 4. Managed platforms

The stack is three ordinary containers, so anything that runs a container runs this.
What follows is the shape rather than a click-by-click, since every console changes.

### AWS

- **Database:** RDS for PostgreSQL 16. Copy the endpoint into `DATABASE_URL`.
- **Containers:** ECS on Fargate, one task definition with the `api` and `web`
  containers. Inside a task they share a network namespace, so nginx reaches the API
  at `127.0.0.1:8000` — change `nginx.conf`'s two `set $api ...` lines accordingly, and
  **delete the `resolver 127.0.0.11` line**, which is Docker's embedded DNS and does
  not exist outside a Compose network. Running them as two services instead means
  Service Connect or an internal load balancer, with the resolver pointed at the VPC
  resolver (`.2` of the VPC CIDR) rather than removed.
- **Ingress:** an Application Load Balancer to the `web` container's port 80. Terminate
  TLS at the ALB; the API already trusts `X-Forwarded-Proto` via uvicorn's
  `--proxy-headers`.
- **Secrets:** `SECRET_KEY` and the database password as Secrets Manager entries
  referenced from the task definition — not as plain environment values in the console,
  which are visible to anyone with read access to the task definition.
- **Health check:** ALB target group on `/health`.

### Azure

- **Database:** Azure Database for PostgreSQL — Flexible Server.
- **Containers:** Container Apps, one app per image, with the API set to internal
  ingress so only the web app can reach it.
- **Secrets:** Container Apps secrets, or Key Vault references.
- **Health check:** the app's own liveness and readiness probes, at the two endpoints
  above.

### Anything with a `postgres://` URL

Render, Railway, Fly.io and Heroku all hand out a URL in that scheme, which SQLAlchemy
2.0 rejects outright as an unknown plugin. `config.py` rewrites it, so it can be used
exactly as given.

---

## 5. Schema changes

There is no migration tool. `app/core/schema.py::ensure_schema` runs on every startup
and does two things: `create_all` for tables that do not exist, then
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for columns added after their table first
shipped. Every statement is safe to re-run, so a fresh clone, the running development
database and a container started from an old volume all converge from the same call.

`create_all` alone would not be enough — it creates missing *tables* but never adds a
column to a table that already exists, so a new column simply never appears on an
existing database, silently, until the first query against it fails.

To run it by hand:

```bash
docker compose exec api python -m scripts.apply_schema
```

**When Alembic arrives**, `ensure_schema` is the single place to retire: stamp the
schema it produces as the baseline revision and delete the column list. That is the
right moment to do it, and it has not been done here — the honest position is that
this handles the two columns the project has needed so far and would not handle a
column rename, a type change or a data migration.

---

## 6. Operational notes

**Logs.** One line per request, carrying the method, path, status, duration and a
request id. The id is also returned in the `X-Request-ID` response header and in the
body of any 500, which is what turns "it broke at about four o'clock" into one `grep`.
nginx forwards its own `$request_id` so both logs share one identifier. Set
`LOG_JSON=true` behind a collector.

```bash
docker compose logs -f api
```

**Backups.** The `db-data` volume is the only state. Everything else — including the
24 MB seeded patent cache — is rebuilt from the image.

```bash
docker compose exec db pg_dump -U postgres innovation_platform > backup.sql
```

**Scaling.** One uvicorn worker per container, so scale by running more containers: a
restart then takes out one worker rather than all of them. Before adding instances,
note that the analysis endpoints are the slow ones and they are slow for reasons more
containers will not fix — see the known limits below.

**Known limits, stated rather than hidden.**

- `analyze_landscape` is declared `async` but does blocking work: a 0.4–1.1 MB
  `json.load` and a SHA-1 over roughly 1,100 records. Inside `asyncio.gather` it holds
  the event loop, so the patent and research halves of a page never truly overlap. An
  in-process memo on `_load_sample` is the cheapest available win on the whole app.
- OpenAlex is fetched per request and never cached, which is the dominant cost in every
  assessment. A short-TTL cache is the highest-value follow-up.
- Patent cache lookups are slug-exact: "Energy Storage" hits, "Li-ion batteries" misses
  into a live search. Admin → Data & sources makes the gaps visible.
