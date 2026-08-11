from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.baby import Baby
from app.models.device import Device
from app.models.user import User
from app.schemas.baby import BabyCreate, BabyOut, BabyUpdate
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/baby", tags=["baby"])

# Product limit: two babies per account. Twins are the case multi-baby exists
# for; higher-order multiples would need this raised here AND in the frontend's
# MAX_BABIES (store/babyStore.ts), which hides the "Add baby" control.
MAX_BABIES_PER_USER = 2


# The app colour is an account-level preference on the user, chosen freely in
# Settings (PATCH /auth/me/preferences). It used to be derived here from the
# baby's gender; the client asked for a free choice instead, and with twins
# there is no per-baby answer anyway. babies.theme_color is now unused.


def _owned_baby(baby_id: int, user: User, db: Session) -> Baby:
    """Fetch a baby, 404ing unless it belongs to the caller.

    Scoped by user_id as well as id so a guessed id from another account is
    indistinguishable from one that doesn't exist.
    """
    baby = db.query(Baby).filter(Baby.id == baby_id, Baby.user_id == user.id).first()
    if not baby:
        raise HTTPException(status_code=404, detail="Baby not found")
    return baby


@router.get("/", response_model=List[BabyOut])
def list_babies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Every baby on the account, oldest profile first so the ordering is stable
    and the first-created baby stays the default selection.

    Returns `[]` rather than 404 when there are none — "no babies yet" is a
    normal state the client handles by routing to setup.
    """
    return (
        db.query(Baby)
        .filter(Baby.user_id == current_user.id)
        .order_by(Baby.id)
        .all()
    )


@router.post("/", response_model=BabyOut, status_code=status.HTTP_201_CREATED)
def create_baby(
    body: BabyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = db.query(Baby).filter(Baby.user_id == current_user.id).count()
    if count >= MAX_BABIES_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"You can add up to {MAX_BABIES_PER_USER} babies.",
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


@router.patch("/{baby_id}", response_model=BabyOut)
def update_baby(
    baby_id: int,
    body: BabyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    baby = _owned_baby(baby_id, current_user, db)
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


@router.delete("/{baby_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_baby(
    baby_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Remove a baby profile.

    Their feeding logs are kept, with `baby_id` set to NULL — deleting a profile
    should not silently destroy a feeding history. Refuses to remove the last
    baby, since the app has no meaningful state with none.
    """
    baby = _owned_baby(baby_id, current_user, db)

    if db.query(Baby).filter(Baby.user_id == current_user.id).count() <= 1:
        raise HTTPException(
            status_code=400,
            detail="You must have at least one baby profile.",
        )

    # Detach rather than cascade-delete: the history stays, unattributed.
    for log in baby.feeding_logs:
        log.baby_id = None
    # Clear any device still pointing at this baby, or the FK blocks the delete.
    db.query(Device).filter(Device.active_baby_id == baby.id).update(
        {Device.active_baby_id: None}
    )
    db.delete(baby)
    db.commit()
    return None
