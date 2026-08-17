import asyncio
import sys

from app.core.database import SessionLocal
from app.models.research_profile import ResearchProfile
from app.services import patents_analysis as pa
from app.services import profile_utils

TOPICS = [
    "battery", "solar energy", "artificial intelligence", "quantum computing",
    "robotics", "renewable energy", "machine learning", "biotechnology",
    "electric vehicle", "gene editing", "semiconductor", "hydrogen fuel",
    "energy storage", "clean energy", "materials science", "photovoltaics",
    "grid technology", "cybersecurity", "nanotechnology", "medical devices",
    "autonomous vehicles", "wind energy", "drug discovery", "wireless communication",
    "fax machine",
]

_REQUEST_GAP = 8


def _profile_fields() -> list[str]:
    """Every exact field spelling users actually have — so their chips resolve to a cache hit."""
    db = SessionLocal()
    try:
        terms: list[str] = []
        for profile in db.query(ResearchProfile).all():
            areas, _fallback = profile_utils.technology_terms(profile)
            terms.extend(areas)
        return terms
    finally:
        db.close()


async def main():
    requested = [a for a in sys.argv[1:] if a.strip()]
    if requested:
        print(f"seeding {len(requested)} requested topic(s) only")

    seen: set[str] = set()
    topics: list[str] = []
    for topic in requested or (TOPICS + _profile_fields()):
        slug = pa._slug(topic)
        if slug not in seen:
            seen.add(slug)
            topics.append(topic)

    ok = 0
    consecutive_failures = 0
    for topic in topics:
        existing = pa._load_cache(topic)
        if existing is not None and existing.get("corpus_total") is not None:
            print(f"skip '{topic}' (already cached)")
            ok += 1
            continue
        if existing is not None:
            print(f"upgrading '{topic}' (cached without a corpus total)")
        try:
            result = await pa._fetch_patents(topic, num=100)
            pa._save_cache(topic, result["patents"], result["corpus_total"])
            total = result["corpus_total"]
            print(f"seeded '{topic}': {len(result['patents'])} sampled of "
                  f"{total if total is not None else 'unknown'} matching")
            ok += 1
            consecutive_failures = 0
        except Exception as exc:
            consecutive_failures += 1
            print(f"FAILED '{topic}': {type(exc).__name__} (source busy — rerun later)")
            if consecutive_failures >= 3:
                print("\nstopping: source is throttling us. Wait a few hours and rerun — "
                      "already-cached topics are skipped, so it resumes where it left off.")
                break
        await asyncio.sleep(_REQUEST_GAP)
    print(f"\ndone: {ok}/{len(topics)} topics cached")


if __name__ == "__main__":
    asyncio.run(main())
