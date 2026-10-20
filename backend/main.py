import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Product, StockAlert
from schemas import BuyRequest, MessageResponse, ProductResponse, RestockRequest
from firebase_service import (
    log_purchase_audit,
    log_warehouse_alert,
    log_restock_audit,
    get_recent_cloud_audits,
    get_firestore_client,
)


def seed_products():
    """Insert starter products once, only when the product table is empty."""
    from database import SessionLocal

    db = SessionLocal()
    try:
        if db.query(Product).count() == 0:
            db.add_all([
                Product(name="Wireless Mouse", description="Simple everyday mouse", price_cents=799, stock=12, threshold=5),
                Product(name="USB-C Cable", description="1 metre charging cable", price_cents=499, stock=8, threshold=3),
                Product(name="Keyboard", description="Compact USB keyboard", price_cents=1499, stock=6, threshold=2),
            ])
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_products()
    # Initialize Firebase Firestore connection on startup
    get_firestore_client()
    yield


app = FastAPI(title="Multi-Cloud Inventory API (AWS + Google Firebase)", version="2.0.0", lifespan=lifespan)

origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "inventory-api",
        "cloud_1": "AWS EC2 + AWS RDS PostgreSQL",
        "cloud_2": "Google Cloud Firebase (Firestore)",
    }


@app.get("/cloud/status")
def cloud_status():
    """Provides architecture status showing Multi-Cloud integration."""
    fb_connected = get_firestore_client() is not None
    return {
        "architecture": "Multi-Cloud Hybrid Inventory Management System",
        "cloud_1": {
            "provider": "Amazon Web Services (AWS)",
            "components": [
                "AWS EC2 (inventory-api-server)",
                "AWS RDS PostgreSQL (inventory-db)",
                "AWS VPC + Security Groups",
            ],
            "role": "Core API server & transactional relational database",
            "status": "active",
        },
        "cloud_2": {
            "provider": "Google Cloud Firebase",
            "components": [
                "Cloud Firestore NoSQL Document Database",
                "Real-time Audit Logs & Warehouse Alerts",
            ],
            "role": "Real-time purchase audit trail & decentralized cloud alerting",
            "status": "connected" if fb_connected else "offline",
        },
    }


@app.get("/cloud/audits")
def get_cloud_audits():
    """Fetch live audit trail directly from Google Cloud Firestore."""
    return get_recent_cloud_audits(limit=20)


@app.get("/products", response_model=list[ProductResponse])
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).order_by(Product.id).all()


@app.post("/store/buy", response_model=MessageResponse)
def buy_product(payload: BuyRequest, db: Session = Depends(get_db)):
    """Store use case: decrement stock in AWS RDS, log purchase audit & alerts to Google Cloud Firestore."""
    product = db.query(Product).filter(Product.id == payload.product_id).with_for_update().first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.stock <= 0:
        raise HTTPException(status_code=400, detail="This product is out of stock")

    product.stock -= 1
    db.commit()

    # Cloud 2: Log real-time audit record to Google Cloud Firestore
    log_purchase_audit(
        product_id=product.id,
        product_name=product.name,
        new_stock=product.stock,
        price_cents=product.price_cents,
    )

    message = f"Purchase successful. {product.name} stock is now {product.stock}."

    if product.stock < product.threshold:
        # Check AWS RDS for active alert
        active_alert = (
            db.query(StockAlert)
            .filter(StockAlert.product_id == product.id, StockAlert.is_resolved.is_(False))
            .first()
        )
        if not active_alert:
            db.add(StockAlert(
                product_id=product.id,
                message=f"Low stock: {product.name} has {product.stock} item(s); threshold is {product.threshold}.",
            ))
            db.commit()

        # Cloud 2: Dispatch low-stock alert to Google Cloud Firestore
        log_warehouse_alert(
            product_id=product.id,
            product_name=product.name,
            stock=product.stock,
            threshold=product.threshold,
        )

        message += " Low-stock notification synced to AWS RDS and Google Cloud Firestore."

    return {"message": message}


@app.get("/warehouse/alerts")
def warehouse_alerts(db: Session = Depends(get_db)):
    """Warehouse use case: show unresolved low-stock alerts."""
    rows = (
        db.query(StockAlert, Product)
        .join(Product, StockAlert.product_id == Product.id)
        .filter(StockAlert.is_resolved.is_(False))
        .order_by(StockAlert.created_at.desc(), StockAlert.id.desc())
        .all()
    )
    return [
        {
            "id": alert.id,
            "product_id": product.id,
            "product_name": product.name,
            "message": alert.message,
            "stock": product.stock,
            "threshold": product.threshold,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
        }
        for alert, product in rows
    ]


@app.post("/warehouse/restock", response_model=MessageResponse)
def restock_product(payload: RestockRequest, db: Session = Depends(get_db)):
    """Warehouse use case: update AWS RDS inventory, resolve alerts in both AWS and Google Cloud Firestore."""
    product = db.query(Product).filter(Product.id == payload.product_id).with_for_update().first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.stock += payload.quantity
    open_alerts = (
        db.query(StockAlert)
        .filter(StockAlert.product_id == product.id, StockAlert.is_resolved.is_(False))
        .all()
    )
    for alert in open_alerts:
        alert.is_resolved = True

    db.commit()

    # Cloud 2: Log restock event & resolve open alerts in Google Cloud Firestore
    log_restock_audit(
        product_id=product.id,
        product_name=product.name,
        quantity=payload.quantity,
        new_stock=product.stock,
    )

    return {
        "message": f"Restocked {product.name} by {payload.quantity}. New stock: {product.stock}. Alerts resolved on AWS & Google Cloud."
    }
