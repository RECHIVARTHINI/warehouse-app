import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

def get_database_url():
    """Load the DB URL from Key Vault in Azure, from .env, or fallback to SQLite for local development."""
    vault_url = os.getenv("KEY_VAULT_URL", "").strip()
    if vault_url:
        secret_name = os.getenv("KEY_VAULT_SECRET_NAME", "DATABASE-URL").strip()
        if not secret_name:
            raise RuntimeError("KEY_VAULT_SECRET_NAME cannot be empty when KEY_VAULT_URL is set.")

        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        credential = DefaultAzureCredential()
        try:
            client = SecretClient(vault_url=vault_url, credential=credential)
            secret = client.get_secret(secret_name)
            database_url = secret.value
        finally:
            credential.close()
        if not database_url:
            raise RuntimeError(f"Key Vault secret '{secret_name}' is empty.")
        return database_url

    return os.getenv("DATABASE_URL", "sqlite:///./inventory.db")


DATABASE_URL = get_database_url()

connect_args = {}
if "sqlite" in DATABASE_URL:
    connect_args = {"check_same_thread": False}
elif "rds.amazonaws.com" in DATABASE_URL:
    connect_args = {"sslmode": "require"}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
