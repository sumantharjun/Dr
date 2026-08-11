from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.baby import Baby
from app.models.user import User
from app.schemas.baby import BabyCreate, BabyOut, BabyUpdate
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/baby", tags=["baby"])


# The app colour is an account-level preference on the user, chosen freely in
# Settings (PATCH /auth/me/preferences). It used to be derived here from the
# baby's gender; the client asked for a free choice instead, and with twins
# there is no per-baby answer anyway. babies.theme_color is now unused.


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
        date_of_birth=body.date_of_birth,
        weight_kg=body.weight_kg,
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
    if body.date_of_birth is not None:
        baby.date_of_birth = body.date_of_birth
    if body.weight_kg is not None:
        baby.weight_kg = body.weight_kg
    db.commit()
    db.refresh(baby)
    return baby
