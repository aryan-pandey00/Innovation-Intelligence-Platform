from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from decimal import Decimal
from app.models.funding import FundingSourceType


class FundingOpportunityBase(BaseModel):
    title: str
    agency: str
    source_type: FundingSourceType
    description: str
    domains: list[str] = []
    keywords: list[str] = []
    eligible_roles: list[str] = []
    countries: list[str] = []
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    currency: str | None = "USD"
    deadline: date | None = None
    url: str | None = None


class FundingOpportunityCreate(FundingOpportunityBase):
    pass


class FundingOpportunityResponse(FundingOpportunityBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LiveOpportunity(BaseModel):
    id: str
    title: str
    agency: str
    source_type: str
    description: str
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    currency: str | None = "USD"
    deadline: date | None = None
    countries: list[str] = []
    url: str | None = None
    live: bool = True
    source_label: str = "Live"
    awarded: bool = False


class FundingRecommendation(BaseModel):
    opportunity: FundingOpportunityResponse
    relevance_score: float
    eligibility: str
    eligible: bool
    matched_terms: list[str] = []
    reasons: list[str] = []


class RankedOpportunity(BaseModel):
    opportunity: dict
    relevance_score: float
    eligibility: str
    eligible: bool
    matched_terms: list[str] = []
    reasons: list[str] = []
