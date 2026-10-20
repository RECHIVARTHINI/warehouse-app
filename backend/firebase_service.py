import os
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

_db = None

def get_firestore_client():
    global _db
    if _db is not None:
        return _db
    
    key_path = os.getenv("FIREBASE_KEY_PATH", os.path.join(os.path.dirname(__file__), "firebase-key.json"))
    if not os.path.exists(key_path):
        return None
        
    try:
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
        _db = firestore.client()
        return _db
    except Exception as e:
        print(f"Warning: Failed to initialize Firebase: {e}")
        return None

def log_purchase_audit(product_id: int, product_name: str, new_stock: int, price_cents: int):
    """Store transaction audit log in Google Cloud Firestore."""
    db = get_firestore_client()
    if not db:
        return None
    try:
        doc_ref = db.collection("purchase_audit_logs").document()
        payload = {
            "transaction_id": doc_ref.id,
            "product_id": product_id,
            "product_name": product_name,
            "remaining_stock": new_stock,
            "price_cents": price_cents,
            "cloud_origin": "AWS EC2 (inventory-api-server)",
            "cloud_database": "Google Cloud Firestore NoSQL",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        doc_ref.set(payload)
        return doc_ref.id
    except Exception as e:
        print(f"Error logging purchase to Firestore: {e}")
        return None

def log_warehouse_alert(product_id: int, product_name: str, stock: int, threshold: int):
    """Store low-stock alert in Google Cloud Firestore."""
    db = get_firestore_client()
    if not db:
        return None
    try:
        doc_ref = db.collection("warehouse_cloud_alerts").document()
        payload = {
            "alert_id": doc_ref.id,
            "product_id": product_id,
            "product_name": product_name,
            "current_stock": stock,
            "threshold": threshold,
            "status": "OPEN",
            "cloud_origin": "AWS EC2 (inventory-api-server)",
            "destination_cloud": "Google Cloud Firebase",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        doc_ref.set(payload)
        return doc_ref.id
    except Exception as e:
        print(f"Error logging alert to Firestore: {e}")
        return None

def log_restock_audit(product_id: int, product_name: str, quantity: int, new_stock: int):
    """Store warehouse restock audit in Google Cloud Firestore and resolve open alerts."""
    db = get_firestore_client()
    if not db:
        return None
    try:
        doc_ref = db.collection("restock_audit_logs").document()
        payload = {
            "restock_id": doc_ref.id,
            "product_id": product_id,
            "product_name": product_name,
            "added_quantity": quantity,
            "new_stock": new_stock,
            "cloud_origin": "AWS EC2 (inventory-api-server)",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        doc_ref.set(payload)
        
        # Mark alerts for this product as resolved in Firestore
        alerts = (
            db.collection("warehouse_cloud_alerts")
            .where(filter=FieldFilter("product_id", "==", product_id))
            .where(filter=FieldFilter("status", "==", "OPEN"))
            .stream()
        )
        for alert in alerts:
            alert.reference.update({"status": "RESOLVED", "resolved_at": datetime.now(timezone.utc).isoformat()})
            
        return doc_ref.id
    except Exception as e:
        print(f"Error logging restock to Firestore: {e}")
        return None

def get_recent_cloud_audits(limit: int = 15):
    """Retrieve live audit logs from Google Cloud Firestore."""
    db = get_firestore_client()
    if not db:
        return []
    try:
        docs = (
            db.collection("purchase_audit_logs")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"Error reading Firestore audit logs: {e}")
        return []
