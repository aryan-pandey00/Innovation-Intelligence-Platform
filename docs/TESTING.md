# Testing

147 tests in `backend/tests/`, run with `pytest`. They finish in roughly two minutes,
and they need a running PostgreSQL.

```bash
cd backend
pip install -r requirements-dev.txt
pytest                  # or: pytest -v, pytest tests/test_notifications.py
```

---

## Why PostgreSQL and not SQLite

Every list column in this schema is `JSONB`. The notification de-duplication is a
Postgres `INSERT ... ON CONFLICT DO NOTHING`. The alert feed orders by `COALESCE` over
timezone-aware timestamps. Running the suite on SQLite would mean replacing all three
with something else — and then the tests would be exercising code the deployment never
runs, which is the one thing a test suite must not do.

So the price is a running database, and the suite says so plainly: if Postgres is
unreachable it **skips with a message naming the reason** rather than failing in a way
that looks like a broken test.

## The test database

Derived by appending `_test` to the configured database name, created at the start of
the session and dropped at the end. It is never the development database — the fixture
refuses to run if the two names match, because tests truncate tables between cases and
would otherwise delete real data on the first run.

Set `TEST_DATABASE_URL` to point somewhere else.

Isolation is by `TRUNCATE ... RESTART IDENTITY CASCADE` after each test, not by an
enclosing transaction that gets rolled back. The route handlers call `db.commit()`
themselves, and wrapping committing code in an outer transaction is the kind of
arrangement that works until one handler opens a savepoint and then fails in a way
nobody can read.

The schema comes from `ensure_schema` — the same function the application runs at
startup — so the tests execute against the schema a deployment actually produces
rather than a `create_all` approximation of it.

---

## What is covered, and why each file exists

| File | Tests | What it pins |
| :-- | --: | :-- |
| `test_startup.py` | 9 | Importing the app opens no database connection; liveness answers without a database; readiness does not; an unhandled error returns a traceable id and nothing else. |
| `test_config.py` | 12 | Three URL schemes reach the installed driver; production refuses the committed signing key; CORS parses from a plain comma list. |
| `test_schema_bootstrap.py` | 5 | The bootstrap is idempotent, and a dropped column is restored — the case `create_all` cannot handle. |
| `test_auth.py` | 10 | Registration, login, and what a token is not good for: forged signature, expired, or belonging to a deleted account. |
| `test_roles_and_privilege.py` | 30 | Every role gate, the full super-admin ladder, and the guards that stop the last administrator deleting themselves. |
| `test_audit.py` | 7 | One row per privileged action, and the row still readable after the user it describes is deleted. |
| `test_funding.py` | 11 | Catalogue round-trip, reversed amount ranges refused, and eligibility computed rather than assumed. |
| `test_analytics_invariants.py` | 11 | The buckets add up to the stated population; three surfaces report one score. |
| `test_notifications.py` | 21 | De-duplication, the match floor, and change detection that stays quiet when it has nothing to compare against. |
| `test_reports.py` | 18 | The spreadsheet and the PDF state the same figures as the screen; identifiers survive the layout whole. |
| `test_security.py` | 9 | A census of every route, credentials never in a payload, no network call from the data-health endpoint. |

### The four tests worth reading first

**`test_importing_the_app_does_not_touch_the_database`** — `ensure_schema(engine)` used
to run at module level, so *importing* the application opened a connection. In a
compose stack the API and Postgres start together, the API lost the race, and the
orchestrator restarted it: a crash loop that reads as a broken image. Runs in a clean
interpreter pointed at a dead port, which is the only place the property is observable.

**`test_a_duplicate_does_not_poison_the_session`** — the worst defect this project had.
`emit()` caught `IntegrityError` around a plain insert, but a failed flush marks the
whole SQLAlchemy session as needing a rollback, so the *next* insert raised
`PendingRollbackError` — a different exception, uncaught, swallowed by the generator's
blanket `except`. After the first duplicate, every remaining alert in the pass silently
vanished. A test that only checked "the duplicate was not inserted twice" would have
passed against the broken version.

**`test_one_scoring_path_across_three_surfaces`** — an owner's best funding match once
read 85% on the admin dashboard and 27% on their own page, because one used
`max(score)` and the other used the shared ordering. This asserts the manager's column,
the admin's summary and the owner's own list agree.

**`test_every_api_route_requires_a_token_unless_it_is_listed_as_public`** — a census
rather than a spot check. Every other test covers a route somebody remembered to think
about; this covers the ones nobody did. A new endpoint written without an
authentication dependency is not a visible mistake — it works perfectly, for everyone.

---

## What is deliberately not tested here

**The four live reports and the analysis pages that read external sources.** They call
OpenAlex and EPO. A suite that fails when an external API is rate-limited is a suite
people learn to ignore, and a green run would then mean nothing. Their shared
machinery — scoring, formatting, export, role gating — is covered through the two
database-only reports.

**The frontend.** There is no component test runner in the project. `npm run build` is
the gate CI uses, and it fails on an unresolved import or a syntax error. Behaviour is
covered end to end through the API tests plus manual review of each page.

**Load and performance.** No numbers are claimed. The DB-only analytics answer in
milliseconds by construction — they make no external call — and the slow paths are
named in `docs/DEPLOYMENT.md` with the reason rather than measured and left
unexplained.

---

## In CI

`.github/workflows/ci.yml` runs the suite against a `postgres:16` service container on
every push, alongside a frontend build and a build of both container images. The Python
version matches `backend/Dockerfile` (3.12), so a dependency that resolves in CI
resolves in the image.
