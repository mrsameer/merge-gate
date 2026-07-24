"""Pydantic models for the order service."""

from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    customer_id: str = Field(min_length=1)
    item: str = Field(min_length=1)
    quantity: int = Field(gt=0)


class Order(OrderCreate):
    id: str
