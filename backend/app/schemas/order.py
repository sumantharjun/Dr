from datetime import datetime
from typing import List
from pydantic import BaseModel


class ProductOut(BaseModel):
    id: int
    name: str
    description: str | None
    price: float
    category: str
    stock: int
    image_url: str | None

    model_config = {"from_attributes": True}


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int


class OrderCreate(BaseModel):
    items: List[OrderItemCreate]


class OrderItemOut(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: float
    product: ProductOut

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: int
    status: str
    total_price: float
    created_at: datetime
    items: List[OrderItemOut]

    model_config = {"from_attributes": True}
