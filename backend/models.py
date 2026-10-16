from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    description = Column(String(300), nullable=False, default="")
    price_cents = Column(Integer, nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    threshold = Column(Integer, nullable=False, default=5)


class StockAlert(Base):
    __tablename__ = "stock_alerts"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    message = Column(String(300), nullable=False)
    is_resolved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
