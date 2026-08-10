"""Sanity-check the term -> CPC map in epo_ops against the live API.

For each mapped term it reports the phrase count next to the CPC count. A good
mapping should be dramatically larger than the phrase count (that was the whole
point) and plausible for the size of the field. A CPC that errors or returns
near-zero is wrong and must be corrected before seeding trusts it.

"""
import asyncio
import sys

import httpx

from app.services import epo_ops


async def main() -> int:
    if not epo_ops.is_configured():
        print("OPS credentials are not set in backend/.env")
        return 1

    wanted = [a for a in sys.argv[1:] if a.strip()]
    terms = wanted or sorted(epo_ops._TERM_CPC)

    print(f"{'term':22} {'phrase':>9} {'cpc':>10}  cpc expression")
    print("-" * 72)

    quota = 5
    async with httpx.AsyncClient(timeout=40) as client:
        for term in terms:
            cpc = epo_ops.cpc_for(term)
            if not cpc:
                print(f"{term:22} {'-':>9} {'-':>10}  (not mapped)")
                continue

            results = {}
            for label, cql in (("phrase", epo_ops._cql_phrase(term)),
                               ("cpc", epo_ops._cql_cpc(cpc))):
                await asyncio.sleep(epo_ops._pace(quota))
                try:
                    results[label], quota = await epo_ops._count(client, cql)
                except epo_ops.OPSUnavailable as exc:
                    results[label] = None
                    if exc.blocked:
                        print(f"\nstopped: {exc}")
                        return 1
                    print(f"    {term} {label}: {exc}")

            p, c = results.get("phrase"), results.get("cpc")
            verdict = ""
            if c is None:
                verdict = "  <-- CPC REJECTED, fix it"
            elif c == 0:
                verdict = "  <-- CPC matches nothing, wrong code"
            elif p is not None and c < p:
                verdict = "  <-- CPC narrower than phrase, suspect"
            print(f"{term:22} {str(p):>9} {str(c):>10}  {cpc}{verdict}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
