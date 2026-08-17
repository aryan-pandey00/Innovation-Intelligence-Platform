from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, date


class PublicationBase(BaseModel):
    title: str
    authors: list[str] = []
    venue: str | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    citation_count: int | None = 0
    abstract: str | None = None


class PublicationCreate(PublicationBase):
    pass


class PublicationUpdate(BaseModel):
    title: str | None = None
    authors: list[str] | None = None
    venue: str | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    citation_count: int | None = None
    abstract: str | None = None


class PublicationResponse(PublicationBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PatentBase(BaseModel):
    title: str
    assignee: str | None = None
    patent_number: str | None = None
    filing_date: date | None = None
    classification: str | None = None
    technology_domain: str | None = None
    citation_count: int | None = 0
    url: str | None = None
    abstract: str | None = None


class PatentCreate(PatentBase):
    pass


class PatentUpdate(BaseModel):
    title: str | None = None
    assignee: str | None = None
    patent_number: str | None = None
    filing_date: date | None = None
    classification: str | None = None
    technology_domain: str | None = None
    citation_count: int | None = None
    url: str | None = None
    abstract: str | None = None


class PatentResponse(PatentBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResearchProfileBase(BaseModel):
    headline: str | None = None
    bio: str | None = None
    research_domains: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    technology_areas: list[str] = Field(default_factory=list)
    organization: str | None = None
    organization_type: str | None = None
    country: str | None = None
    website: str | None = None
    orcid_id: str | None = None


class ResearchProfileCreate(ResearchProfileBase):
    pass


class ResearchProfileUpdate(BaseModel):
    headline: str | None = None
    bio: str | None = None
    research_domains: list[str] | None = None
    keywords: list[str] | None = None
    technology_areas: list[str] | None = None
    organization: str | None = None
    organization_type: str | None = None
    country: str | None = None
    website: str | None = None
    orcid_id: str | None = None


class ResearchProfileResponse(ResearchProfileBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    publications: list[PublicationResponse] = []
    patents: list[PatentResponse] = []

    model_config = ConfigDict(from_attributes=True)
