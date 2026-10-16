from pydantic import BaseModel, Field


class BuyRequest(BaseModel):
    product_id: int


class RestockRequest(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=10000)


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str
    price_cents: int
    stock: int
    threshold: int


class MessageResponse(BaseModel):
    message: str
