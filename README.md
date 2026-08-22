# AI-Powered Research Funding & Innovation Intelligence Platform

A platform that helps researchers, startup founders and R&D teams find relevant
funding, track research trends, and assess the patent and innovation landscape of a
technology.

**Live demo:** <https://innovation-intelligence-platform.vercel.app/> ·
**API docs:** [`/docs`](https://innovation-intelligence-platform.vercel.app/docs)

> Free-tier hosting sleeps when idle, so the first request after a quiet period takes
> up to a minute to wake the API. The page itself loads immediately.

---

## Project Overview

The platform connects three things that normally sit apart: **academic research
output**, **patent activity**, and **funding opportunities**. A user describes their
research profile once, and every module then works from it — recommending grants,
charting how their field is moving, showing who already holds the IP, scoring how
strong their position is, and suggesting a route to market.

**Core approach**

1. **Profile-driven** — domains, keywords, role and region are matched against
   funding programmes using weighted scoring and TF-IDF text similarity.
2. **Live data, honestly labelled** — research and patent figures come from real
   APIs, and every card states what it was measured on. Nothing derived from a
   sample is presented as a whole-field fact.
3. **Cached, not fetched** — slow external sources are seeded to disk ahead of time,
   so no web request waits on a rate-limited API.

---

## Data Sources

| Source | Used for |
| :--- | :--- |
| **OpenAlex API** | Research publication counts, trends, topics, citations |
| **EPO Open Patent Services** | Real patent counts per field and per year, applicant records, classification codes |
| **Grants.gov / World Bank / UKRI** | Live funding opportunity search |
| **40 curated funding opportunities** | Seeded dataset (NSF, NIH, Horizon Europe, SBIR, climate and AI grants) used by the recommendation engine, since no single free API covers global grants comprehensively |
| **Google Patents** | Fallback patent retrieval where OPS is unavailable |

**On patent sampling.** EPO returns a count for a whole field in one cheap request,
but reading patent records is slow. So counts use the **entire corpus** (e.g. 502,434
for grid technology), while anything needing the text inside a patent uses a
**date-balanced sample of 1,100 records** — 100 per year across 11 years, so no
single year dominates. **23 technology topics are pre-seeded**, and the app runs from
that cache without any API keys.

---

## Milestones

### Milestone 1 — Platform, Security & Profiles
- Decoupled **FastAPI + React (Vite)** architecture.
- **JWT authentication with role-based access control** — `researcher`,
  `startup_founder`, `innovation_manager`, `admin`. Self-registration is limited to
  the first two; elevated roles are assigned deliberately.
- Full **research profile lifecycle**: domains, keywords, technology areas,
  publications, patents, region.
- Relational schema (SQLAlchemy) for users, profiles, publications and funding.

### Milestone 2 — Funding Discovery & Trend Analytics
- **Funding module** with search, filters, detail views, and a **recommendation
  engine** ranking grants on domain overlap, role eligibility, geography and keyword
  relevance, with eligibility checked rather than assumed.
- **Research Trends dashboard** on live OpenAlex data — publication growth over a
  12-year window, top sub-field distribution, emerging-topic growth rates, and
  high-impact papers.
- **Admin panel** for user management, database statistics and seeding.

### Milestone 3 — Patent Analytics & Innovation Intelligence
- **Patent Landscape** — field size, filing trend, and a growth figure computed from
  3-year averages at each end rather than single endpoints. An **Innovation Map**
  groups patents into themes using **TF-IDF + K-means clustering**, named by their
  shared classification code. **Top patent holders** are ranked by their *true*
  count across the whole field, queried per applicant from EPO.
- **Technology Intelligence** — places a field as **Emerging / Growing / Mature**,
  compares research growth against patent growth as a ratio of multipliers, charts
  both series indexed to their own peak, and reports ownership concentration and the
  mix of organisation types.
- **Innovation Assessment** — a 0–100 score from **five weighted factors**
  (research novelty 30%, patent strength 20%, market potential 20%, technology
  maturity 15%, funding relevance 15%, per the project specification). Corpus sizes
  are normalised on a **log scale** and growth through **tanh**, so no factor
  saturates and becomes a constant. Only portfolio items matching the technology are
  counted.
- **Commercialization** — recommends a pathway (spin-out, partnership, licensing or
  validate-first) from the field's lifecycle stage, then emits a rule-based set of
  recommendations split into **"Do next"** (carrying a deadline or risk) and
  **"Worth knowing"** (context), including a prior-art warning where publishing
  before filing would put a patent at risk.
- **Derived-analysis caching** — clustering, applicant tallies and ownership are
  computed at seed time and stored against a content hash, keeping page loads fast
  regardless of sample size.

### Milestone 4 — Roles, Alerts, Reports & Deployment

- **Four roles, each with its own platform.** `researcher` and `startup_founder` own a
  portfolio; `innovation_manager` and `admin` own none and are given surfaces built for
  what they actually do — a pipeline triage list and platform health respectively. The
  two owner roles get identical scores from identical modules and **different advice**:
  a researcher is told to talk to their technology transfer office, a founder to talk to
  a patent attorney before the next public demo.
- **Privileged access as data, not as a constant.** Super-admin is a flag on an
  administrator rather than a fifth role, so no existing role gate needs widening.
  Granting it requires an existing super-admin *and* an administrator target; the last
  holder cannot be removed, and a role change on a flagged account is refused rather
  than silently clearing it. Every such action is written to an **audit trail** that
  deliberately has no foreign keys, so a record outlives the account it describes.
- **Notification & alert system.** New and closing grants above the platform's single
  definition of an actionable match, risks in your own portfolio, and movement in the
  fields you named. Generated when the feed is read rather than on a timer, de-duplicated
  in the database, and dated **when the thing happened** rather than when you looked.
  Change detection stores a previous reading per topic, so a first reading alerts nobody
  and an unreliable, sample-derived series never becomes a baseline.
- **Reports & export.** Nine reports, role-scoped, each rendered three ways — on screen,
  as a spreadsheet, as a PDF — from **one** structure built on the server, so an exported
  file cannot state a figure the screen never showed. Spreadsheet figures are real numbers
  with display formats, so they sort and total.
- **Account recovery without email.** This platform sends no email, so a forgotten
  password is recovered by an administrator's judgement rather than a link. The
  locked-out browser holds a server-minted random claim, two security questions give the
  administrator something to weigh, and approval releases the claim so the new password
  is set in the page that never closed. **The answers are evidence, not a key** — getting
  both right approves nothing by itself, because two questions are a few hundred
  plausible guesses and would otherwise be a weaker door than the password they protect.
  An account that never set questions is told so plainly and offered a written appeal
  instead of being asked to answer questions it never chose.
- **Disclosure and abuse resistance.** Sign-in spends the same time on an unknown
  address as on a real one, so response time cannot confirm who is registered; the
  recovery flow answers an invented address exactly as it answers a real one at every
  step, including the status poll; and rate limits are keyed to the *effect* — guessing,
  queue creation, redemption — rather than one limit per endpoint. Every limiter is
  derived from the module rather than listed by hand, so a new one cannot be left out.
- **Integration, testing and deployment.** 298 committed tests against a real
  PostgreSQL; Docker images for the API and the web tier with a Compose stack; GitHub
  Actions running tests, the frontend build and both image builds; liveness and readiness
  probes; and structured request logging with a correlation id carried from nginx through
  to the body of any 500. A **route census** walks every endpoint the application serves
  and fails if one answers an unauthenticated caller, or if an `/api/admin` route answers
  an ordinary account — because the endpoints nobody remembered to think about are the
  ones a hand-written list of checks always misses.

---

## Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React (Vite), React Router, Recharts, Axios, vanilla CSS with design tokens |
| **Backend** | Python, FastAPI, SQLAlchemy 2, Pydantic v2, HTTPX (async), PyJWT, Passlib (bcrypt) |
| **ML / Analytics** | scikit-learn — TF-IDF vectorisation, K-means clustering, cosine similarity |
| **Database** | PostgreSQL (JSONB columns for domains, keywords and eligibility) via SQLAlchemy |
| **Export** | openpyxl (spreadsheets), ReportLab (PDF) |
| **External APIs** | OpenAlex, EPO Open Patent Services, Grants.gov, World Bank, UKRI |
| **Testing & CI** | pytest against a real PostgreSQL, GitHub Actions |
| **Deployment** | Docker, Docker Compose, nginx, uvicorn |

---

## Quick Start

Two ways in. The containerised one needs only Docker; the manual one is what you want
for day-to-day development.

### Option A — Docker (the whole stack)

**Prerequisites:** Docker with Compose v2.

```bash
cp .env.example .env
# Fill in POSTGRES_PASSWORD and SECRET_KEY. Compose refuses to start without them.
python -c "import secrets; print(secrets.token_urlsafe(48))"   # generate SECRET_KEY

docker compose up --build
docker compose exec api python -m scripts.seed_funding
docker compose exec api python -m scripts.create_admin you@example.org "Your Name" <password> --super
```

Open **http://localhost:8080** — API documentation is proxied at `/docs`.

Full detail, including AWS and Azure, in **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**.

### Option B — run it directly

**Prerequisites:** Python 3.10+, Node.js 18+, PostgreSQL 14+

Create the database and put its URL in `backend/.env` (see `.env.example`).

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate | Linux/macOS: source venv/bin/activate
pip install -r requirements.txt

python -m scripts.apply_schema        # create tables and add any new columns
python -m scripts.seed_funding        # 40 curated funding opportunities
python -m scripts.create_admin you@example.org "Your Name" <password> --super

uvicorn app.main:app --reload
```

Runs on `http://localhost:8000`, with Swagger docs at `/docs`. The schema is also
brought up to date automatically at startup, so `apply_schema` is only needed when you
want to do it separately.

```bash
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:5173` and proxies `/api` to the backend.

---

## Tests

298 tests across 15 files, roughly two minutes, against a real PostgreSQL — the schema
uses `JSONB` and the code uses Postgres-only `INSERT ... ON CONFLICT`, so a substitute
database would mean testing code the deployment never runs.

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

A separate `<database>_test` database is created and dropped by the suite; it refuses to
run against the development database. See **[docs/TESTING.md](docs/TESTING.md)** for what
is covered, what is deliberately not, and the four tests worth reading first.

---

## Documentation

| | |
| :--- | :--- |
| **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)** | What each of the four roles can see and do, and how to read every figure. |
| **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** | Containers, settings, health probes, AWS and Azure, schema changes, known limits. |
| **[docs/TESTING.md](docs/TESTING.md)** | How to run the suite, what it covers, and why it needs PostgreSQL. |
| `/docs` on a running server | Interactive OpenAPI documentation for every endpoint. |

### Optional — refreshing patent data

The patent modules read from the cache in `backend/app/data/`, so they work out of
the box. To rebuild or add a technology, put EPO OPS credentials in `backend/.env`
(see `.env.example`) and run:

```bash
python -m scripts.seed_patent_series --all       # all default topics
python -m scripts.seed_patent_series "solid-state battery"
```

OPS limits searches to a few per minute, so a topic takes a few minutes. The script
is resumable — finished topics are skipped.
