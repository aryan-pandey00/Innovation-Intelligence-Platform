"""The funding catalogue and the recommendation engine's contract."""
import datetime as dt

from app.models.funding import FundingOpportunity
from app.models.user import UserRole
from app.services import funding_reco
from tests.conftest import auth_header, make_opportunity, make_profile, make_user

GRANT = {
    "title": "Battery Storage Research Award",
    "agency": "Test Energy Agency",
    "source_type": "government_grant",
    "description": "Supports research into grid-scale battery storage.",
    "domains": ["energy"],
    "keywords": ["battery", "storage"],
    "eligible_roles": ["researcher"],
    "countries": ["United States"],
    "amount_min": 50000,
    "amount_max": 250000,
    "currency": "USD",
    "deadline": "2027-06-30",
}


def test_only_an_administrator_may_add_a_grant(client, db):
    make_user(db, "owner@example.org", UserRole.RESEARCHER)
    make_user(db, "manager@example.org", UserRole.INNOVATION_MANAGER)
    for who in ("owner@example.org", "manager@example.org"):
        assert client.post("/api/funding", json=GRANT,
                           headers=auth_header(client, who)).status_code == 403
    assert db.query(FundingOpportunity).count() == 0


def test_a_grant_survives_a_full_round_trip(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    headers = auth_header(client, "admin@example.org")

    created = client.post("/api/funding", json=GRANT, headers=headers)
    assert created.status_code == 201, created.text
    opp = created.json()
    assert opp["domains"] == ["energy"]

    listed = client.get("/api/funding", headers=headers).json()
    assert [row["id"] for row in listed] == [opp["id"]]
    assert client.get(f"/api/funding/{opp['id']}", headers=headers).status_code == 200

    corrected = client.put(f"/api/funding/{opp['id']}",
                           json={**GRANT, "deadline": "2028-01-31",
                                 "keywords": ["battery"]},
                           headers=headers)
    assert corrected.status_code == 200
    updated = corrected.json()
    assert updated["id"] == opp["id"]
    assert updated["created_at"] == opp["created_at"]
    assert updated["deadline"] == "2028-01-31"
    assert updated["keywords"] == ["battery"]

    assert client.delete(f"/api/funding/{opp['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/funding/{opp['id']}", headers=headers).status_code == 404


def test_a_reversed_amount_range_is_refused_on_both_write_paths(client, db):
    """It would render as "USD 500K–100K" and score as though it were a real range."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    headers = auth_header(client, "admin@example.org")
    reversed_range = {**GRANT, "amount_min": 500000, "amount_max": 100000}

    assert client.post("/api/funding", json=reversed_range,
                       headers=headers).status_code == 400

    existing = client.post("/api/funding", json=GRANT, headers=headers).json()
    assert client.put(f"/api/funding/{existing['id']}", json=reversed_range,
                      headers=headers).status_code == 400


def test_updating_or_deleting_a_grant_that_is_not_there_is_a_404(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    headers = auth_header(client, "admin@example.org")
    assert client.put("/api/funding/99999", json=GRANT, headers=headers).status_code == 404
    assert client.delete("/api/funding/99999", headers=headers).status_code == 404


def test_search_matches_the_title_and_the_agency(client, db):
    make_user(db, "owner@example.org", UserRole.RESEARCHER)
    headers = auth_header(client, "owner@example.org")
    make_opportunity(db, title="Quantum Sensing Fund", agency="DARPA")
    make_opportunity(db, title="Battery Storage Award", agency="Test Energy Agency")

    found = client.get("/api/funding/search?q=battery", headers=headers).json()
    assert [row["title"] for row in found] == ["Battery Storage Award"]


def test_recommendations_need_a_profile_and_say_so(client, db):
    """A 400 here is a state the page turns into guidance, not a server fault."""
    make_user(db, "owner@example.org", UserRole.RESEARCHER)
    response = client.get("/api/funding/recommendations",
                          headers=auth_header(client, "owner@example.org"))
    assert response.status_code == 400


def test_a_matching_grant_outranks_an_unrelated_one(client, db):
    user = make_user(db, "owner@example.org", UserRole.RESEARCHER)
    make_profile(db, user, domains=["energy"], keywords=["battery", "storage"])
    make_opportunity(db, title="Unrelated Marine Biology Grant", domains=["biology"],
                     keywords=["coral", "reef"])
    make_opportunity(db, title="Battery Storage Award", domains=["energy"],
                     keywords=["battery", "storage"])

    ranked = client.get("/api/funding/recommendations",
                        headers=auth_header(client, "owner@example.org")).json()
    assert ranked[0]["opportunity"]["title"] == "Battery Storage Award"
    assert ranked[0]["relevance_score"] > ranked[-1]["relevance_score"]


def test_a_role_restricted_grant_is_ineligible_rather_than_hidden(client, db):
    """Ineligible rows stay in the list with a reason."""
    user = make_user(db, "founder@example.org", UserRole.STARTUP_FOUNDER)
    make_profile(db, user, domains=["energy"], keywords=["battery"])
    make_opportunity(db, title="Academics Only Award", eligible_roles=["researcher"])

    ranked = client.get("/api/funding/recommendations",
                        headers=auth_header(client, "founder@example.org")).json()
    row = next(r for r in ranked if r["opportunity"]["title"] == "Academics Only Award")
    assert row["eligibility"] == funding_reco.INELIGIBLE
    assert row["eligible"] is False
    assert row["reasons"], "an exclusion has to say what excluded them"


def test_a_country_restriction_is_checked_against_the_profile(client, db):
    user = make_user(db, "abroad@example.org", UserRole.RESEARCHER)
    make_profile(db, user, country="India", domains=["energy"], keywords=["battery"])
    make_opportunity(db, title="US Only Award", countries=["United States"])

    ranked = client.get("/api/funding/recommendations",
                        headers=auth_header(client, "abroad@example.org")).json()
    row = next(r for r in ranked if r["opportunity"]["title"] == "US Only Award")
    assert row["eligibility"] == funding_reco.INELIGIBLE


def test_a_closed_deadline_makes_a_grant_ineligible_for_everyone(client, db):
    user = make_user(db, "owner@example.org", UserRole.RESEARCHER)
    make_profile(db, user, domains=["energy"], keywords=["battery", "storage"])
    make_opportunity(db, title="Closed Last Year", domains=["energy"],
                     keywords=["battery", "storage"],
                     deadline=dt.date.today() - dt.timedelta(days=1))

    ranked = client.get("/api/funding/recommendations",
                        headers=auth_header(client, "owner@example.org")).json()
    row = next(r for r in ranked if r["opportunity"]["title"] == "Closed Last Year")
    assert row["eligibility"] == funding_reco.INELIGIBLE


def test_every_grant_is_ranked_so_zero_means_measured_not_missing(client, db):
    """The catalogue view needs "reaches nobody" to differ from "was not scored"."""
    user = make_user(db, "owner@example.org", UserRole.RESEARCHER)
    make_profile(db, user, domains=["energy"], keywords=["battery"])
    for i in range(4):
        make_opportunity(db, title=f"Grant {i}", domains=["unrelated"],
                         keywords=[f"term{i}"])

    ranked = client.get("/api/funding/recommendations",
                        headers=auth_header(client, "owner@example.org")).json()
    assert len(ranked) == 4
    assert all(row["relevance_score"] >= 0 for row in ranked)
