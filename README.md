# Innovation Intelligence Platform

A research funding and innovation intelligence platform for researchers, startup
founders and R&D teams. It answers four questions about a technology field in one
place: **who is funding it, where the research is going, who already owns the patents,
and whether it is worth commercialising.**

Built solo, end to end — database, API, analytics, frontend, tests and deployment.

**Live demo:** <https://innovation-intelligence-platform.vercel.app/> &nbsp;·&nbsp;
**API docs:** [`/docs`](https://innovation-intelligence-platform.vercel.app/docs)

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-Vite-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-JSONB-4169E1?logo=postgresql&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?logo=scikitlearn&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/tests-299-success)

> The API is on free-tier hosting that sleeps when idle, so the first request after a
> quiet period takes up to a minute to wake it. The page itself loads immediately.

![Landing page](docs/images/landing_page.png)

![Researcher dashboard](docs/images/dashboard.png)

---

## What it does

Research output, patent activity and funding opportunities normally live in three
separate places, and a researcher deciding whether to pursue a technology has to
cross-reference them by hand. This platform joins them.

A user describes their research profile once — subject areas, keywords, technology
areas, region, existing publications and patents. Every part of the platform then works
from that profile rather than asking again.

| The user wants to know | What the platform gives them |
| :--- | :--- |
| What can I apply for? | Funding matched against their profile on subject overlap, region and keyword similarity, with eligibility actually checked rather than assumed |
| Is this field growing? | A 12-year publication trend, which sub-fields dominate, which topics are rising fastest, and the most-cited papers |
| Who already owns this? | How many patents exist in the field, how filings are trending, which organisations hold the most, and the main themes they group into |
| How mature is the field? | An Emerging, Growing or Mature verdict, research growth set against patent growth, and how concentrated the ownership is |
| How strong is my position? | A 0–100 innovation score built from five weighted factors, each one visible on its own |
| What should I do next? | A recommended route to market — spin-out, partnership, licensing, or validate first — and a dated action list |
| Can I show someone? | Nine reports tailored to the user's role, on screen and downloadable as a spreadsheet or a PDF |

Every figure states what it was measured on. Nothing worked out from a sample is
presented as a fact about the whole field.

### Four roles, four different surfaces

| Role | Has a portfolio | What they see |
| :--- | :---: | :--- |
| `researcher` | Yes | Funding, trends, patents, assessment, commercialisation |
| `startup_founder` | Yes | The same modules, with founder-facing advice |
| `innovation_manager` | No | A triage list across the innovators they oversee |
| `admin` | No | User management, platform health, database statistics |

The two roles that own a portfolio get identical scores from identical modules and
**different advice** — a researcher is told to contact their technology transfer office,
a founder to contact a patent attorney before the next public demo. Anyone can register
as one of those two roles; the other two are assigned.

---

## Technology stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React (Vite), Recharts |
| **Backend** | FastAPI, SQLAlchemy 2, Pydantic v2, async HTTPX |
| **Database** | PostgreSQL, with JSONB columns for subject areas, keywords and eligibility rules |
| **Auth** | JWT with role-based access control, bcrypt password hashing |
| **Analytics** | scikit-learn — TF-IDF, K-means clustering, cosine similarity |
| **Testing & deployment** | pytest against a real PostgreSQL, GitHub Actions, Docker Compose, nginx |

**Where the data comes from.** OpenAlex for publications, trends and citations. EPO Open
Patent Services for patent counts, applicants and classification codes. Grants.gov,
World Bank and UKRI for live funding search, plus **40 curated funding opportunities**
covering NSF, NIH, Horizon Europe, SBIR and climate and AI grants, because no single
free API covers global grants comprehensively. **23 technology topics come pre-seeded**,
so the platform runs with no API keys required.

---

## How it was built

The five decisions that shaped the project.

**Patent counts and patent text come from different data.** EPO returns a count for a
whole field in one cheap request, but reading the records themselves is slow. So counts
use the entire field, while anything that needs the text inside a patent uses a sample
of 1,100 records — 100 per year across 11 years, so no single year dominates. Every
figure on screen says which of the two it came from.

**The slow analysis runs once, not on every request.** Clustering, counting patents per
organisation and working out ownership concentration all happen ahead of time and are
stored against a fingerprint of their input, so pages load at the same speed whether the
sample is small or large.

**The security test reads the routing table rather than a checklist.** It walks every
endpoint the application actually serves and fails the build if one of them answers a
caller who is not signed in, or if an admin route answers an ordinary account. A
hand-written list of things to check always misses the endpoint nobody remembered.

**Reports are built once on the server and rendered three ways.** The screen, the
spreadsheet and the PDF all read from the same structure, so a downloaded file cannot
show a number the screen never did. Spreadsheet cells are real numbers with formatting
applied, so they still sort and total.

**Tests run against real PostgreSQL, including in CI.** The database uses JSONB columns
and PostgreSQL-only insert behaviour, so swapping in SQLite for the test suite would
mean testing code the deployed version never runs.

---

## Running it locally

### With Docker

**Needs:** Docker with Compose v2.

```bash
cp .env.example .env
# Fill in POSTGRES_PASSWORD and SECRET_KEY. Compose refuses to start without them.
python -c "import secrets; print(secrets.token_urlsafe(48))"   # generate SECRET_KEY

docker compose up --build
docker compose exec api python -m scripts.seed_funding
docker compose exec api python -m scripts.create_admin you@example.org "Your Name" <password> --super
```

Open **http://localhost:8080**. API documentation is proxied at `/docs`.

### Without Docker

**Needs:** Python 3.10+, Node.js 18+, PostgreSQL 14+. Create the database and put its
URL in `backend/.env` (see `.env.example`).

```bash
cd backend
python -m venv venv && venv\Scripts\activate     # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
python -m scripts.seed_funding                   # 40 curated funding opportunities
python -m scripts.create_admin you@example.org "Your Name" <password> --super
uvicorn app.main:app --reload                    # http://localhost:8000, docs at /docs

cd ../frontend
npm install && npm run dev                       # http://localhost:5173, proxies /api
```

The database tables are created and kept up to date at startup.

### Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

**299 tests across 15 files**, roughly two minutes. The suite builds and drops its own
separate test database and refuses to run against the development one. It covers sign-in
and roles, privilege escalation, rate limiting, the audit trail, notifications, report
generation, database setup, and the analytics figures themselves.

---

## Documentation

| | |
| :--- | :--- |
| **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)** | What each role can see and do, and how to read every figure |
| **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** | Containers, settings, health checks, AWS and Azure, known limits |
| **[docs/TESTING.md](docs/TESTING.md)** | How to run the suite, what it covers, and why it needs PostgreSQL |
| `/docs` on a running server | Interactive API documentation for every endpoint |

Behind it: 69 API endpoints across 13 route modules, 21 analytics service modules, and
17 frontend pages.
