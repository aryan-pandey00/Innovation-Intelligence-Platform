# AI-Powered Research Funding & Innovation Intelligence Platform

A platform that helps researchers, startup founders and R&D teams find relevant
funding, track research trends, and assess the patent and innovation landscape of a
technology.

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

---

## Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React (Vite), React Router, Recharts, Axios, vanilla CSS with design tokens |
| **Backend** | Python, FastAPI, SQLAlchemy, Pydantic v2, HTTPX (async), PyJWT, Passlib |
| **ML / Analytics** | scikit-learn — TF-IDF vectorisation, K-means clustering, cosine similarity |
| **Database** | SQLite (development) / PostgreSQL-ready SQLAlchemy engine |
| **External APIs** | OpenAlex, EPO Open Patent Services, Grants.gov, World Bank, UKRI |

---

## Quick Start

**Prerequisites:** Python 3.10+, Node.js 18+

### Backend

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate | Linux/macOS: source venv/bin/activate
pip install -r requirements.txt

python -m scripts.seed_funding        # 40 curated funding opportunities
uvicorn app.main:app --reload
```

Runs on `http://localhost:8000`, with Swagger docs at `/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:5173`.

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
