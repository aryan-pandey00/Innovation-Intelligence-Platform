"""Platform analytics: the arithmetic that has to add up, and the single scoring path."""
from app.models.user import UserRole
from app.services import platform_analytics
from tests.conftest import auth_header, make_opportunity, make_profile, make_user


def _populated(db):
    """Three owners — one matching, one unrelated, one with no portfolio — plus staff."""
    matching = make_user(db, "matching@example.org", UserRole.RESEARCHER)
    make_profile(db, matching, domains=["energy"], keywords=["battery", "storage"],
                 technology_areas=["energy storage"])

    unrelated = make_user(db, "unrelated@example.org", UserRole.STARTUP_FOUNDER)
    make_profile(db, unrelated, domains=["marine biology"], keywords=["coral"],
                 technology_areas=[])

    no_portfolio = make_user(db, "empty@example.org", UserRole.RESEARCHER)

    admin = make_user(db, "admin@example.org", UserRole.ADMIN)
    manager = make_user(db, "manager@example.org", UserRole.INNOVATION_MANAGER)

    make_opportunity(db, title="Battery Storage Award", domains=["energy"],
                     keywords=["battery", "storage"])
    make_opportunity(db, title="Unreachable Astronomy Fund", domains=["astronomy"],
                     keywords=["telescope", "spectroscopy"])
    return matching, unrelated, no_portfolio, admin, manager


def test_the_matching_buckets_account_for_every_owner(db):
    """strong + weak_only + none + without_profile == the stated population."""
    _populated(db)
    stats = platform_analytics.recommendation_stats(db)
    population = stats["population"]
    matching = stats["matching"]

    total = (matching["strong"] + matching["weak_only"] + matching["none"]
             + population["without_profile"])
    assert total == population["total"], (
        f"buckets sum to {total} but the population is {population['total']}: "
        "a card built on this would describe people who are not in it"
    )


def test_the_population_names_itself(db):
    """The label ships with the count so no card can invent a denominator."""
    _populated(db)
    stats = platform_analytics.recommendation_stats(db)
    assert stats["population"]["label"] == "portfolio owners"
    assert stats["population"]["total"] == 3
    assert stats["matching"]["threshold"] == platform_analytics.STRONG_MATCH


def test_the_median_carries_the_population_it_was_measured_on(db):
    """The bug this exists to stop."""
    _populated(db)
    matching = platform_analytics.recommendation_stats(db)["matching"]
    population = platform_analytics.recommendation_stats(db)["population"]

    assert matching["median_population"] == matching["strong"] + matching["weak_only"]
    assert matching["median_population"] != population["with_profile"], (
        "this fixture has an owner who matched nothing, so the two must differ; "
        "if they cannot differ the assertion above proves nothing"
    )


def test_staff_are_counted_as_accounts_and_never_as_a_failure(db):
    _populated(db)
    stats = platform_analytics.recommendation_stats(db)
    accounts = stats["accounts"]
    assert accounts["total"] == 5
    assert accounts["owners"] == 3
    assert accounts["staff"] == 2
    assert accounts["owners"] + accounts["staff"] == accounts["total"]
    assert stats["population"]["without_profile"] == 1


def test_every_grant_appears_in_reach_including_the_ones_nobody_matches(db):
    """A sparse list cannot tell "reaches nobody" from "was not measured"."""
    _populated(db)
    stats = platform_analytics.recommendation_stats(db)
    reach = {row["id"]: row["owners"] for row in stats["reach"]}
    assert len(reach) == stats["opportunities"]["total"] == 2
    assert min(reach.values()) == 0, "the unreachable grant must be listed at zero"
    assert stats["opportunities"]["unreachable"] >= 1
    assert (stats["opportunities"]["reachable"]
            + stats["opportunities"]["unreachable"]) == stats["opportunities"]["total"]


def test_the_pipeline_roster_covers_the_owners_with_portfolios(db):
    _populated(db)
    stats = platform_analytics.pipeline_stats(db)
    assert stats["innovators"] == 3
    assert stats["with_profile"] == 2
    assert stats["attention"]["no_portfolio"] == 1
    assert stats["attention"]["no_focus"] == 1
    assert len(stats["roster"]) == 2


def test_technology_areas_are_counted_per_person_not_per_mention(db):
    """One user listing the same field twice must not inflate the pipeline."""
    user = make_user(db, "repeater@example.org", UserRole.RESEARCHER)
    make_profile(db, user, technology_areas=["Energy Storage", "energy storage"])
    stats = platform_analytics.pipeline_stats(db)
    counts = {row["name"]: row["users"] for row in stats["technologies"]}
    assert counts == {"Energy Storage": 1}


def test_one_scoring_path_across_three_surfaces(client, db):
    """The manager's column, the admin's summary and the owner's own page agree."""
    matching, *_ = _populated(db)

    roster = platform_analytics.pipeline_stats(db)["roster"]
    manager_view = next(r for r in roster if r["user_id"] == matching.id)["best_match"]

    admin_stats = platform_analytics.recommendation_stats(db)
    assert (manager_view["score"] >= platform_analytics.STRONG_MATCH) == (
        admin_stats["matching"]["strong"] >= 1)

    own_page = client.get("/api/funding/recommendations",
                          headers=auth_header(client, "matching@example.org")).json()
    assert round(own_page[0]["relevance_score"], 1) == manager_view["score"]
    assert own_page[0]["opportunity"]["title"] == manager_view["title"]
    assert own_page[0]["eligibility"] == manager_view["eligibility"]


def test_a_zero_score_is_not_reported_as_a_best_match(db):
    """Every grant is ranked, so there is always a row."""
    user = make_user(db, "nomatch@example.org", UserRole.RESEARCHER)
    make_profile(db, user, domains=["marine biology"], keywords=["coral"])
    make_opportunity(db, title="Astronomy Fund", domains=["astronomy"],
                     keywords=["telescope"])

    stats = platform_analytics.pipeline_stats(db)
    assert stats["roster"][0]["best_match"] is None
    assert stats["attention"]["no_strong_match"] == 1


def test_the_funding_total_is_a_number_not_a_decimal_string(db):
    """`amount_max` is Numeric, so an unconverted sum reaches the client as text and."""
    _populated(db)
    total = platform_analytics.pipeline_stats(db)["funding"]["total_available"]
    assert isinstance(total, int)
    assert total > 0


def test_a_single_agency_per_grant_produces_no_top_agency_ranking(db):
    """At one grant each, "NSF (1), NIH (1)" implies a ranking that does not exist."""
    _populated(db)
    assert platform_analytics.pipeline_stats(db)["funding"]["top_agencies"] == []


def test_a_repeating_funder_does_produce_a_ranking(db):
    for i in range(platform_analytics._AGENCY_REPEATS):
        make_opportunity(db, title=f"NSF Award {i}", agency="NSF")
    top = platform_analytics.pipeline_stats(db)["funding"]["top_agencies"]
    assert top and top[0]["name"] == "NSF"
