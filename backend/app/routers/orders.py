from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.order import Order, OrderItem, Product
from app.models.user import User
from app.schemas.order import OrderCreate, OrderOut, ProductOut
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderStatusUpdate(BaseModel):
    status: Literal["cancelled"]


@router.get("/products", response_model=List[ProductOut])
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).filter(Product.stock > 0).all()


@router.post("/", response_model=OrderOut, status_code=201)
def place_order(
    body: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total = 0.0
    items = []
    for item in body.items:
        if item.quantity < 1:
            raise HTTPException(status_code=400, detail="Quantity must be at least 1")
        # SELECT FOR UPDATE prevents concurrent orders from overselling
        product = (
            db.query(Product)
            .filter(Product.id == item.product_id)
            .with_for_update()
            .first()
        )
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        if product.stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for '{product.name}'")
        total += product.price * item.quantity
        items.append(
            OrderItem(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=product.price,
            )
        )
        product.stock -= item.quantity

    order = Order(user_id=current_user.id, status="pending", total_price=round(total, 2))
    db.add(order)
    db.flush()
    for item in items:
        item.order_id = order.id
        db.add(item)
    db.commit()
    db.refresh(order)
    return order


@router.get("/", response_model=List[OrderOut])
def list_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Order)
        .filter(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(
        Order.id == order_id, Order.user_id == current_user.id
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a pending or confirmed order and restore stock atomically."""
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == current_user.id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in ("pending", "confirmed"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel an order that is already '{order.status}'",
        )
    for item in order.items:
        product = (
            db.query(Product)
            .filter(Product.id == item.product_id)
            .with_for_update()
            .first()
        )
        if product:
            product.stock += item.quantity
    order.status = "cancelled"
    db.commit()
    db.refresh(order)
    return order
