from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.baby import Baby
from app.models.user import User
from app.schemas.baby import BabyCreate, BabyOut, BabyUpdate
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/baby", tags=["baby"])


def _default_theme_for_gender(gender: str) -> str:
    return "blue" if gender == "male" else "pink"


@router.get("/", response_model=BabyOut)
def get_baby(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    baby = db.query(Baby).filter(Baby.user_id == current_user.id).first()
    if not baby:
        raise HTTPException(status_code=404, detail="Baby profile not set")
    return baby


@router.post("/", response_model=BabyOut, status_code=status.HTTP_201_CREATED)
def create_baby(
    body: BabyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(Baby).filter(Baby.user_id == current_user.id).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Baby profile already exists. Use PATCH to update.",
        )
    baby = Baby(
        user_id=current_user.id,
        name=body.name,
        gender=body.gender,
        weight_kg=body.weight_kg,
        theme_color=body.theme_color or _default_theme_for_gender(body.gender),
    )
    db.add(baby)
    db.commit()
    db.refresh(baby)
    return baby


@router.patch("/", response_model=BabyOut)
def update_baby(
    body: BabyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    baby = db.query(Baby).filter(Baby.user_id == current_user.id).first()
    if not baby:
        raise HTTPException(status_code=404, detail="Baby profile not set")
    if body.name is not None:
        baby.name = body.name
    if body.gender is not None:
        baby.gender = body.gender
    if body.weight_kg is not None:
        baby.weight_kg = body.weight_kg
    if body.theme_color is not None:
        baby.theme_color = body.theme_color
    db.commit()
    db.refresh(baby)
    return baby
