"""Commercialisation recommendations."""
RESEARCHER = "researcher"
FOUNDER = "startup_founder"


def _voice(user_role: str | None) -> str:
    """Which of the two owner roles is reading."""
    return FOUNDER if user_role == FOUNDER else RESEARCHER


_PATHWAYS = {
    "Emerging": {
        RESEARCHER: {
            "title": "Spin-out, once it is protected",
            "detail": "The IP position is still open, and filing early gives you "
                      "room that a crowded field would not. Your institution most "
                      "likely owns what you file, so disclose before you publish.",
        },
        FOUNDER: {
            "title": "File early, then raise",
            "detail": "The IP position is still open, and filing early gives you "
                      "room that a crowded field would not. A filing of your own "
                      "is also what makes the next round defensible.",
        },
    },
    "Growing": {
        RESEARCHER: {
            "title": "Industry partnership",
            "detail": "Capable partners already exist, and the technology is past "
                      "proving itself. Sponsored or joint work reaches a market "
                      "you would otherwise have to build.",
        },
        FOUNDER: {
            "title": "Pilot with an incumbent",
            "detail": "Capable partners already exist, and the technology is past "
                      "proving itself. A paid pilot proves demand faster and more "
                      "cheaply than raising against a forecast.",
        },
    },
    "Mature": {
        RESEARCHER: {
            "title": "Licence out",
            "detail": "The incumbents hold the ground, so licensing to one of them "
                      "moves faster than competing with them.",
        },
        FOUNDER: {
            "title": "Licence in, or find the gap",
            "detail": "The incumbents hold the ground, so a frontal build is "
                      "expensive. Licensing in, or serving a segment they ignore, "
                      "is the cheaper way in.",
        },
    },
    "Developing": {
        RESEARCHER: {
            "title": "Validate first",
            "detail": "Too little patent data could be matched to this technology, "
                      "so the IP risk is unmeasured. Confirm what exists before a "
                      "grant application commits you to it.",
        },
        FOUNDER: {
            "title": "Validate first",
            "detail": "Too little patent data could be matched to this technology, "
                      "so the IP risk is unmeasured. Confirm what exists before you "
                      "commit runway to it.",
        },
    },
}

_VOICE = {
    RESEARCHER: {
        "artefact_action": "Build a prototype, not another paper",
        "off_field_action": "Publish here, or import work we have missed",
        "no_work_reading": "Peer-reviewed results are what make a licensee or "
                           "investor take a technology seriously.",
        "protect_action": "Ask your technology transfer office what is still "
                          "protectable",
    },
    FOUNDER: {
        "artefact_action": "Put it in front of a pilot customer",
        "off_field_action": "Show results in this field, or import work we have "
                            "missed",
        "no_work_reading": "Evidence in the field you are selling into is what "
                           "makes an investor or licensee take a claim seriously.",
        "protect_action": "Ask a patent attorney what is still protectable before "
                          "the next public demo",
    },
}

NOW = "now"
CONTEXT = "context"


def _fmt(n) -> str:
    return f"{n:,}" if isinstance(n, (int, float)) else str(n)


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _date(value) -> str:
    """`15 Nov 2026`, for use mid-sentence."""
    try:
        return f"{value.day} {_MONTHS[value.month - 1]} {value.year}"
    except (AttributeError, IndexError, TypeError):
        return str(value)


def _pct(n) -> str:
    """Whole-number signed percentage: year-on-year counts carry no decimal."""
    if n is None:
        return "unchanged"
    v = round(float(n))
    return f"{'+' if v > 0 else ''}{v}%"


def recommend(score: dict, funding_recs: list[dict],
              publications=None, patents=None,
              user_role: str | None = None) -> dict:
    voice = _voice(user_role)
    v = _VOICE[voice]
    signals = score["signals"]
    stage = signals["stage"]
    assignees = signals.get("top_assignees") or []
    patent_total = signals.get("patent_total") or 0
    patent_growth = signals.get("patent_growth") or 0
    busiest = signals.get("busiest_year")
    history_reliable = signals.get("patent_history_reliable", False)
    sample_size = signals.get("patent_sample_size") or 0

    n_pubs = len(publications or [])
    n_patents = len(patents or [])
    top_citations = max((p.citation_count or 0 for p in (publications or [])), default=0)

    held_pubs = signals.get("portfolio_publications", n_pubs)
    held_patents = signals.get("portfolio_patents", n_patents)

    maturity = next((c["score"] for c in score["components"]
                     if c["key"] == "technology_maturity"), 50)

    research_growth = signals.get("research_growth")

    momentum_card = history_reliable and bool(patent_growth)

    template = _PATHWAYS.get(stage, _PATHWAYS["Developing"])[voice]
    pathway = {
        "title": template["title"],
        "detail": template["detail"],
        "signals": [
            {"label": "Lifecycle stage", "value": stage},
            {"label": "Research growth", "value": _pct(research_growth)},
            {"label": "Patent growth",
             "value": _pct(patent_growth) if history_reliable else "not measurable yet"},
        ],
    }
    recommendations = []

    def card(title, stat, reading, *, priority, facts=None, items=None,
             action=None, link=None, deadline=None):
        return {"title": title, "stat": stat, "facts": facts or [],
                "items": items or [], "reading": reading, "action": action,
                "priority": priority, "link": link, "deadline": deadline}

    if maturity >= 75:
        recommendations.append(card(
            "Ready for product development",
            {"value": _fmt(patent_total), "label": "patents already cover this area"},
            "The science is settled enough that you compete on execution.",
            facts=([f"busiest year was {busiest}"]
                   if busiest and not momentum_card else None),
            action="Prioritise a prototype and a pilot deployment",
            priority=NOW,
            link=None,
        ))
    elif n_pubs > 0:
        facts = []
        if top_citations:
            facts.append(f"{_fmt(top_citations)} citations on the strongest")
        if held_pubs > n_pubs:
            facts.append(f"{held_pubs - n_pubs} more cover other fields")
        recommendations.append(card(
            "Build the evidence into an artefact",
            {"value": str(n_pubs),
             "label": f"publication{'' if n_pubs == 1 else 's'} on this technology"},
            "The evidence exists. What is missing is something you can demonstrate.",
            facts=facts,
            action=v["artefact_action"],
            priority=NOW,
            link={"to": "/portfolio", "label": "Review your portfolio"},
        ))
    elif held_pubs > 0:
        recommendations.append(card(
            "No published work in this field yet",
            {"value": "0", "label": "of your publications cover this technology"},
            f"Your {held_pubs} publication{'' if held_pubs == 1 else 's'} "
            f"cover{'s' if held_pubs == 1 else ''} other fields. A licensee or "
            f"investor will want results in this one.",
            action=v["off_field_action"],
            priority=NOW,
            link={"to": "/portfolio", "label": "Check your portfolio"},
        ))
    else:
        recommendations.append(card(
            "No publications on record",
            {"value": "0", "label": "publications in your portfolio"},
            v["no_work_reading"],
            action="Add or import your existing work",
            priority=NOW,
            link={"to": "/portfolio", "label": "Add your publications"},
        ))

    if n_pubs > 0 and n_patents == 0 and patent_total > 0:
        recommendations.append(card(
            "Published in this field, but holding no patents",
            {"value": _fmt(patent_total), "label": "patents in this field, none yours"},
            "Publishing before filing can count as prior art against your own "
            "application, and Europe allows no grace period.",
            action=v["protect_action"],
            priority=NOW,
            link={"to": "/patents", "label": "See what is already filed"},
        ))
    elif n_patents > 0:
        facts = [f"in a field of {_fmt(patent_total)}"]
        if held_patents > n_patents:
            facts.append(f"{held_patents - n_patents} more cover other fields")
        recommendations.append(card(
            "IP available to license out",
            {"value": str(n_patents),
             "label": f"patent{'' if n_patents == 1 else 's'} you hold here"},
            "That is a position to license from, not only to license into.",
            facts=facts,
            action="Approach the organisations below as licensees, not only partners",
            priority=NOW,
            link={"to": "/portfolio", "label": "Review your patents"},
        ))

    if momentum_card:
        rising = patent_growth > 0
        recommendations.append(card(
            f"Patent activity is {'rising' if rising else 'falling'}",
            {"value": _pct(patent_growth), "label": "change in filings over the decade"},
            "The field is still opening up." if rising else
            "A cooling field can mean a solved problem or a dead end — worth "
            "knowing which before investing.",
            facts=[f"peaked in {busiest}"] if busiest else None,
            priority=CONTEXT,
            link={"to": "/technology", "label": "See the activity over time"},
        ))

    if assignees:
        named = assignees[:3]
        on_corpus = assignees[0].get("basis") == "corpus"
        if on_corpus:
            held = sum(a["corpus_count"] for a in named)
            stat = {"value": _fmt(held),
                    "label": f"patents held by these three, of {_fmt(patent_total)}"}
        else:
            appearances = sum(a.get("count") or 0 for a in named)
            stat = {"value": _fmt(appearances),
                    "label": f"appearances across the {_fmt(sample_size)} patents read"}
        recommendations.append(card(
            "Organisations already active here",
            stat,
            "These are the natural first calls for co-development, licensing or "
            "acquisition.",
            items=[{
                "name": a["assignee"],
                "kind": a.get("kind"),
                "country": a.get("country"),
                "value": _fmt(a["corpus_count"] if on_corpus else (a.get("count") or 0)),
            } for a in named],
            priority=CONTEXT,
            link={"to": "/patents", "label": "See who holds the IP"},
        ))

    if funding_recs:
        top = max(funding_recs, key=lambda r: r.get("relevance_score") or 0)
        opp = top["opportunity"]
        pct = round(top.get("relevance_score", 0))
        recommendations.append(card(
            "Fund the next stage",
            {"value": f"{pct}%", "label": "match to your profile"},
            "It can carry proof-of-concept or commercialisation work.",
            facts=[f"“{opp.title}” — {opp.agency}"],
            action=(f"Apply before {_date(opp.deadline)}" if opp.deadline
                    else "Check the eligibility terms"),
            priority=NOW,
            link={"to": "/funding", "label": "See all matched grants"},
            deadline=opp.deadline.isoformat() if opp.deadline else None,
        ))

    recommendations.sort(key=lambda r: (r["priority"] != NOW, r["deadline"] is None))

    return {"pathway": pathway, "recommendations": recommendations}
