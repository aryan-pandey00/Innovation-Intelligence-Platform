"""Build real per-year patent counts and a record sample from EPO OPS."""
import asyncio
import sys

from app.core.database import SessionLocal
from app.models.research_profile import ResearchProfile
from app.services import epo_ops
from app.services import patents_analysis as pa
from app.services import profile_utils

CORE_TOPICS = [
    "energy storage", "battery", "solar energy", "electric vehicle",
    "machine learning", "artificial intelligence", "quantum computing",
    "semiconductor", "robotics", "biotechnology",
]

EXTRA_TOPICS = [
    "renewable energy", "gene editing", "hydrogen fuel", "clean energy",
    "photovoltaics", "grid technology", "cybersecurity", "nanotechnology",
    "medical devices", "autonomous vehicles", "wind energy", "drug discovery",
    "wireless communication",
]

PER_YEAR_SAMPLE = 100

_COUNT_BASIS = "raw-epodoc"


async def _recount(topic: str, sample: dict, corpus_total: int | None,
                   force: bool = False) -> bool:
    """Refetch this sample's applicant counts."""
    candidates = pa.count_candidates(sample["records"])
    resuming = sample.get("count_basis") == _COUNT_BASIS and not force
    counts = dict(sample.get("applicant_counts") or {}) if resuming else {}
    done = set(sample.get("counted_names") or []) if resuming else set()
    todo = len(candidates) - len(done)
    if todo <= 0:
        return True
    print(f"    {todo} of {len(candidates)} candidates to count "
          f"(~{todo * 14 / 60:.0f} min)", flush=True)

    blocked = False
    try:
        await epo_ops.applicant_counts(topic, candidates, ceiling=corpus_total,
                                       counts=counts, done=done)
    except epo_ops.OPSUnavailable as exc:
        print(f"    applicant counts stopped after {len(done)}: {exc}")
        blocked = exc.blocked

    sample["applicant_counts"] = counts
    sample["counted_names"] = sorted(done)
    sample["count_basis"] = _COUNT_BASIS
    sample["candidates_tested"] = len(done)
    pa.save_sample(topic, sample)
    shown = sorted(counts.items(), key=lambda kv: -kv[1])[:3]
    print(f"    {len(counts)}/{len(done)} resolved: "
          + ", ".join(f"{n} {c:,}" for n, c in shown))
    return not blocked


async def _counts_only(topics: list[str], force: bool) -> int:
    """Recount applicants against existing samples."""
    done = skipped = 0
    for i, topic in enumerate(topics, 1):
        sample = pa._load_sample(topic)
        if sample is None:
            print(f"[{i}/{len(topics)}] skip '{topic}' (no sample yet)")
            skipped += 1
            continue
        series = pa._load_series(topic) or {}
        print(f"[{i}/{len(topics)}] '{topic}' — {len(sample['records'])} records, "
              f"field {series.get('total')}", flush=True)
        if not await _recount(topic, sample, series.get("total"), force):
            print("    stopping — rerun later, finished topics are skipped")
            break
        pa.build_derived(topic, sample["records"],
                         sample.get("applicant_counts"), series.get("total"),
                         sample.get("candidates_tested"))
        done += 1

    print(f"\ndone: {done} recounted, {skipped} skipped")
    return 0


def _profile_fields() -> list[str]:
    """Technology areas real users have, so their chips hit the cache."""
    db = SessionLocal()
    try:
        terms: list[str] = []
        for profile in db.query(ResearchProfile).all():
            areas, _fallback = profile_utils.technology_terms(profile)
            terms.extend(areas)
        return terms
    finally:
        db.close()


async def main() -> int:
    args = [a for a in sys.argv[1:] if a.strip()]
    force = "--force" in args
    everything = "--all" in args
    counts_only = "--counts-only" in args
    requested = [a for a in args if not a.startswith("--")]
    default_topics = CORE_TOPICS + (EXTRA_TOPICS if everything else [])

    if not epo_ops.is_configured():
        print("OPS_CONSUMER_KEY / OPS_CONSUMER_SECRET are not set in backend/.env")
        return 1

    seen: set[str] = set()
    topics: list[str] = []
    for topic in requested or (default_topics + _profile_fields()):
        slug = pa._slug(topic)
        if slug not in seen:
            seen.add(slug)
            topics.append(topic)

    if counts_only:
        print(f"recounting applicants for {len(topics)} topic(s)\n")
        return await _counts_only(topics, force)

    print(f"{len(topics)} topic(s) to build; roughly 2 minutes each\n")

    done = failed = 0
    for i, topic in enumerate(topics, 1):
        existing = pa._load_series(topic)
        expected_basis = epo_ops.base_query(topic)[1]
        stale = existing is not None and existing.get("query_basis") != expected_basis
        need_counts = force or existing is None or stale
        need_sample = force or pa._load_sample(topic) is None

        if not need_counts and not need_sample:
            print(f"[{i}/{len(topics)}] skip '{topic}' (already built)")
            done += 1
            continue

        what = "counts+sample" if need_counts else "sample only"
        note = " [stale basis]" if stale else ""
        print(f"[{i}/{len(topics)}] building '{topic}' ({what}){note} ...", flush=True)
        try:
            if need_counts:
                series = await epo_ops.publication_counts(topic)
            else:
                series = existing
        except epo_ops.OPSUnavailable as exc:
            failed += 1
            print(f"    FAILED: {exc}")
            if exc.blocked:
                if exc.retry_after:
                    secs, ms = exc.retry_after, exc.retry_after / 1000
                    print(f"    OPS asked us to wait {exc.retry_after:.0f} "
                          f"(≈{ms / 60:.0f} min if milliseconds, "
                          f"≈{secs / 3600:.1f} h if seconds)")
                print("    stopping — rerun later, finished topics are skipped")
                break
            continue

        if need_counts:
            series["source"] = "epo_ops"
            pa.save_series(topic, series)
            counts = [p["count"] for p in series["by_year"]]
            print(f"    total {series['total']} via {series['query_basis']}, "
                  f"years {series['by_year'][0]['year']}-{series['by_year'][-1]['year']}, "
                  f"per-year {min(counts)}..{max(counts)}")

        if not need_sample:
            done += 1
            continue

        try:
            sample = await epo_ops.sample_records(topic, series["by_year"],
                                                 per_year=PER_YEAR_SAMPLE)
            named = len({r["assignee"] for r in sample["records"] if r["assignee"]})
            print(f"    sample {len(sample['records'])} records across "
                  f"{len(sample['years_covered'])} years, {named} distinct applicants")

            if not await _recount(topic, sample, series.get("total")):
                pa.save_sample(topic, sample)
                print("    stopping — rerun later")
                break

            pa.save_sample(topic, sample)
            pa.build_derived(topic, sample["records"],
                             sample.get("applicant_counts"), series.get("total"),
                             sample.get("candidates_tested"))
        except epo_ops.OPSUnavailable as exc:
            print(f"    sample skipped: {exc}")
            if exc.blocked:
                print("    stopping — rerun later")
                break
        done += 1

    print(f"\ndone: {done} built/skipped, {failed} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
