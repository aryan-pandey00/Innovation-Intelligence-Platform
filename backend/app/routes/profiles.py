from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.research_profile import ResearchProfile, Publication, Patent
from app.schemas.research_profile import (
    ResearchProfileCreate, ResearchProfileUpdate, ResearchProfileResponse,
    PublicationCreate, PublicationUpdate, PublicationResponse,
    PatentCreate, PatentUpdate, PatentResponse,
)

router = APIRouter(prefix="/api/profiles", tags=["Research Profiles"])


def _get_owned_profile(db: Session, user: User) -> ResearchProfile:
    profile = db.query(ResearchProfile).filter(
        ResearchProfile.user_id == user.id).first()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research profile not found. Create one first with POST /api/profiles/me.",
        )
    return profile


@router.get("/me", response_model=ResearchProfileResponse)
def get_my_profile(current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    return _get_owned_profile(db, current_user)


@router.post("/me", response_model=ResearchProfileResponse,
             status_code=status.HTTP_201_CREATED)

def create_my_profile(data: ResearchProfileCreate,
                      current_user: User = Depends(require_role(
                          UserRole.RESEARCHER, UserRole.STARTUP_FOUNDER)),
                      db: Session = Depends(get_db)):
    """Only the roles that own a portfolio may create one."""
    existing = db.query(ResearchProfile).filter(
        ResearchProfile.user_id == current_user.id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile already exists. Use PUT /api/profiles/me to update it.",
        )
    profile = ResearchProfile(user_id=current_user.id, **data.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/me", response_model=ResearchProfileResponse)
def update_my_profile(data: ResearchProfileUpdate,
                      current_user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    profile = _get_owned_profile(db, current_user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/{user_id}", response_model=ResearchProfileResponse)
def get_profile_by_user(user_id: int,
                        _mgr: User = Depends(require_role(
                            UserRole.ADMIN, UserRole.INNOVATION_MANAGER)),
                        db: Session = Depends(get_db)):
    profile = db.query(ResearchProfile).filter(
        ResearchProfile.user_id == user_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.get("/me/publications", response_model=list[PublicationResponse])
def list_publications(current_user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    profile = _get_owned_profile(db, current_user)
    return profile.publications


@router.post("/me/publications", response_model=PublicationResponse,
             status_code=status.HTTP_201_CREATED)

def add_publication(data: PublicationCreate,
                    current_user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    profile = _get_owned_profile(db, current_user)
    pub = Publication(profile_id=profile.id, **data.model_dump())
    db.add(pub)
    db.commit()
    db.refresh(pub)
    return pub


@router.put("/me/publications/{pub_id}", response_model=PublicationResponse)
def update_publication(pub_id: int, data: PublicationUpdate,
                       current_user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    profile = _get_owned_profile(db, current_user)
    pub = db.query(Publication).filter(
        Publication.id == pub_id, Publication.profile_id == profile.id).first()
    if pub is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(pub, field, value)
    db.commit()
    db.refresh(pub)
    return pub


@router.delete("/me/publications/{pub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_publication(pub_id: int,
                       current_user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    profile = _get_owned_profile(db, current_user)
    pub = db.query(Publication).filter(
        Publication.id == pub_id, Publication.profile_id == profile.id).first()
    if pub is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    db.delete(pub)
    db.commit()


@router.get("/me/patents", response_model=list[PatentResponse])
def list_patents(current_user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    profile = _get_owned_profile(db, current_user)
    return profile.patents


@router.post("/me/patents", response_model=PatentResponse,
             status_code=status.HTTP_201_CREATED)

def add_patent(data: PatentCreate,
               current_user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    profile = _get_owned_profile(db, current_user)
    patent = Patent(profile_id=profile.id, **data.model_dump())
    db.add(patent)
    db.commit()
    db.refresh(patent)
    return patent


@router.put("/me/patents/{patent_id}", response_model=PatentResponse)
def update_patent(patent_id: int, data: PatentUpdate,
                  current_user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    profile = _get_owned_profile(db, current_user)
    patent = db.query(Patent).filter(
        Patent.id == patent_id, Patent.profile_id == profile.id).first()
    if patent is None:
        raise HTTPException(status_code=404, detail="Patent not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(patent, field, value)
    db.commit()
    db.refresh(patent)
    return patent


@router.delete("/me/patents/{patent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patent(patent_id: int,
                  current_user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    profile = _get_owned_profile(db, current_user)
    patent = db.query(Patent).filter(
        Patent.id == patent_id, Patent.profile_id == profile.id).first()
    if patent is None:
        raise HTTPException(status_code=404, detail="Patent not found")
    db.delete(patent)
    db.commit()
