# User guide

Four roles, and each one sees a different platform. This guide is written per role,
because "what can I do here" has four different answers.

Everything the platform tells you is labelled with what it was measured on. Where a
figure comes from a sample rather than a whole field, the card says so — that is a
deliberate rule, not an occasional caveat.

---

## The four roles at a glance

| | Researcher | Startup founder | Innovation manager | Administrator |
| :-- | :-: | :-: | :-: | :-: |
| Owns a portfolio | ✅ | ✅ | — | — |
| Dashboard | own analysis | own analysis | pipeline triage | platform health |
| Funding Discovery | ✅ with recommendations | ✅ with recommendations | browse only | via Admin → Catalogue |
| Research Trends | ✅ | ✅ | — | — |
| Patent Landscape · Technology Intelligence | ✅ own field | ✅ own field | ✅ by query | — |
| Innovation Assessment · Commercialization | ✅ | ✅ | via Assess | — |
| Reports · Alerts · Profile | ✅ | ✅ | ✅ | ✅ |
| Admin Panel | — | — | — | ✅ |

**Researcher and startup founder** get the same modules, and the same numbers from
them — but different advice. A researcher with a strong position is told to talk to
their technology transfer office; a founder is told to talk to a patent attorney before
the next public demo. The score is identical; the recommended next step is not.

**Sign-up is limited to the two owner roles.** Innovation manager and administrator are
assigned by an administrator, and the first administrator is created from a shell — the
application can never be its own root of trust.

---

## If you are a researcher or a startup founder

### Start with your portfolio

**My Portfolio** is where everything else comes from. Fill in:

- **Research domains** — your discipline, e.g. *energy*, *materials science*.
- **Keywords** — what you actually work on, e.g. *solid-state electrolyte*.
- **Technology areas** — the specific technology, e.g. *energy storage*. This is the
  one that unlocks the patent and innovation modules, because a discipline makes a poor
  patent query and the platform will not pretend otherwise.
- **Country** — used to check eligibility for location-restricted funding.
- **Publications and patents** — optional, and they change the analysis: your own work
  in a field counts towards your position in it.

Without a technology area, the analysis pages will say so and point you back here
rather than showing an empty chart.

### Funding Discovery

**Recommended** ranks every grant in the catalogue against your profile on domain
overlap, keyword match, text similarity, role and country. Each row shows a match
percentage and its eligibility:

- **Eligible** — your role and country both satisfied.
- **Unconfirmed** — the grant is country-restricted and your profile has no country.
  Set one and it resolves either way.
- **Ruled out** — with the reason. Ruled-out grants stay in the list. Hiding them is
  what makes people ask why a grant they can see on the funder's own site is missing.

**40% or more** is what the platform treats as a match worth acting on. That one number
is used everywhere — it is also the floor for an alert, so you are not interrupted about
a 27% match.

**Browse** is the whole catalogue, unranked. **Live** searches Grants.gov, the World
Bank and UKRI as you ask.

### Research Trends

Publication volume across a 12-year window, the busiest sub-fields, which topics are
rising fastest, and the most-cited recent work — from OpenAlex, on the field in your
profile or any field you type.

### Patent Landscape

How large the field is, how filings have moved, and who holds the IP.

- **Field size** is the whole corpus — every patent EPO can count.
- **The Innovation Map** groups patents into themes with TF-IDF and K-means, each theme
  named by the classification code its members share.
- **Top holders** are ranked by their true count across the whole field, queried per
  applicant — not by their share of a sample.
- **Growth** compares three-year averages at each end rather than two single years, so
  one unusual year cannot invent a trend.

Where a figure comes from the 1,100-record sample, the card says so.

### Technology Intelligence

Places a field as **Emerging**, **Growing** or **Mature**, and compares research growth
against patent growth as a ratio of multipliers — which tells you whether the science or
the IP is running ahead. Both series are charted indexed to their own peak, so two
quantities of very different size can be read on one axis.

### Innovation Assessment

A score out of 100 from five weighted factors: research novelty 30%, patent strength
20%, market potential 20%, technology maturity 15%, funding relevance 15%. Each factor
shows what it contributed and what it was computed from.

Corpus sizes are normalised on a log scale and growth through `tanh`, so no factor
saturates into a constant. Only the portfolio items that actually match the technology
are counted — listing unrelated work does not raise the score.

### Commercialization

The recommended route to market — spin out, partner, licence, or validate first — chosen
from the field's lifecycle stage and your own position in it. Then a split list:

- **Do next** — carries a deadline or a risk.
- **Worth knowing** — context.

Including a prior-art warning if you have publications in a field where you hold nothing
filed, because publishing before filing can cost you the patent.

### Alerts

Generated when you open the page, not on a timer. Three kinds:

- Grants that match your profile and are newly added or closing soon.
- Risks in your own portfolio.
- Movement in the fields you named.

Each alert is dated **when the thing happened**, not when you looked. Grouped into
**Needs attention** and **Worth knowing**. The first reading of a field never produces
an alert — there is nothing to compare it against yet, and inventing a comparison would
be dishonest.

### Reports

Any analysis, written down: on screen, as a spreadsheet, or as a PDF. All three are
renderings of one structure built on the server, so the file cannot say something the
screen did not. Numbers in the spreadsheet are real numbers, so they sort and total.

---

## If you are an innovation manager

You run a pipeline; you do not have a portfolio of your own.

**Dashboard** is a triage list. **Monitored Innovators** covers every researcher and
founder on the platform — there is no manager-to-innovator assignment in the schema, and
the wording says so rather than implying one. Each row shows their focus and their best
funding match, sorted by score with unscoreable rows last. Above it, the three things
you can act on: who needs a portfolio, who needs a technology area, and who has no match
worth acting on.

**Assess** on any row runs the full innovation assessment using *that innovator's*
portfolio and *their* role. This matters: running the same query from your own account
would score the own-work factors at zero and produce a misleadingly low number for a
field you do not personally work in. It takes a second or two per innovator, which is
why it is behind a click rather than on the dashboard.

**Patent Landscape** and **Technology Intelligence** work by query. Since you have no
profile, the search prompt is the normal way in rather than a missing prerequisite — and
the field chips show what your innovators work on.

**Funding Discovery** is browse and search only. Recommendations need a portfolio.

---

## If you are an administrator

You run the platform. You do not have a portfolio, and the platform will not create one
for you.

**Dashboard** — platform health. How many accounts, and how well the recommendation
engine is reaching the people it is for. That population is **portfolio owners only**:
staff are counted as accounts but are never a denominator, because counting them among
the people who have not built a portfolio turns your own colleagues into a failure
statistic.

**Admin Panel** has three tabs, each its own URL so it can be linked and survives a
reload:

- **Accounts** — assign roles, delete accounts, read the audit log of who changed whose
  access. A staff row shows "No portfolio" rather than a link that can only 404.
- **Catalogue** — add, correct and remove funding opportunities, with a **Reach** column
  showing how many owners each grant actually matches. Filters for *Reaching nobody* and
  *Closed*. A grant with no domains and no keywords cannot score above 40 no matter what
  else it says, and a past deadline rules it out for everyone — both stated in the form's
  help text.
- **Data & sources** — which external sources are configured, which technologies are
  cached, which caches are stale, and which fields a live portfolio names with no corpus
  behind them. That last list is the actual answer to "why is this page empty".

This page reads disk and configuration only and makes **no network call**, so a
rate-limited source can never take the admin dashboard down. It reports whether a
source is *configured* as a yes or no — never the key, and never a truncation of one.

**Broadcasts** — a platform message to everyone or to chosen roles, from the Alerts page.
Sending the same message twice reaches only the accounts that did not already have it, so
it is safe to re-send after new people sign up.

### The super-admin

A flag on an administrator, not a fifth role. Only a super-admin can create or remove
another administrator, and only a super-admin can pass the flag on — and only to an
account that is already an administrator, so the tier cannot be skipped.

Guards that exist so nobody can lock the platform:

- The last super-admin cannot have the flag removed, including by themselves. Step down
  only once someone else holds it.
- The last administrator cannot delete their own account.
- A super-admin's role cannot be changed while the flag is set. It is **refused**, not
  silently cleared — a privilege change should never be a side effect of something else.

Every one of these actions is written to the audit log with both email addresses, and the
record survives the deletion of the account it describes.

The first super-admin comes from a shell:

```bash
python -m scripts.create_admin you@example.org "Your Name" <password> --super
```

---

## Two things that apply to everyone

**Your session** lasts 60 minutes by default. Your role is re-verified against the server
when the app loads, so an account whose role changed does not keep the old sidebar until
the next sign-in.

**Deleting your account** removes your portfolio, publications, patents and alerts. The
audit record of administrative actions remains, deliberately — that is what an audit log
is for.
