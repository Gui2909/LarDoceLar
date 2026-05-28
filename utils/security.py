import hashlib
import secrets
from hashlib import sha256

from fastapi import Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from models.cash_session import CashSession
from models.order_items import OrderItem
from models.orders import Order
from models.user import User
from models.user_session import UserSession


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_hash(password: str) -> str:
    """Legacy SHA-256 hashing (for compatibility)."""
    return sha256(password.encode("utf-8")).hexdigest()


def hash_password(password: str, salt: bytes = None) -> str:
    """Secure password hashing using PBKDF2-HMAC-SHA256 with 100,000 iterations and 16-byte salt."""
    if salt is None:
        salt = secrets.token_bytes(16)
    hash_bytes = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return f"pbkdf2_sha256$100000${salt.hex()}${hash_bytes.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verifies a password against its PBKDF2 hash, falling back to legacy SHA-256 if needed."""
    if not hashed.startswith("pbkdf2_sha256$"):
        return make_hash(password) == hashed
    try:
        parts = hashed.split("$")
        if len(parts) != 4:
            return False
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        stored_hash = parts[3]
        hash_bytes = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hash_bytes.hex() == stored_hash
    except Exception:
        return False


def get_current_user(
    db: Session = Depends(get_db),
    x_token: str | None = Header(default=None),
):
    """Retrieves the currently authenticated user from the database-backed session."""
    if not x_token:
        raise HTTPException(status_code=401, detail="Token ausente")
    session = db.query(UserSession).filter(UserSession.token == x_token).first()
    if session is None:
        raise HTTPException(status_code=401, detail="Token invalido")
    current_user = db.query(User).filter(User.id == session.user_id).first()
    if current_user is None:
        raise HTTPException(status_code=401, detail="Usuario do token nao encontrado")
    return current_user


def require_roles(current_user: User, roles: set[str]):
    """Ensures the authenticated user has one of the allowed roles."""
    if current_user.role.lower() not in roles:
        raise HTTPException(status_code=403, detail="Sem permissao para esta operacao")


def recalculate_order_total(db: Session, order_id: int) -> float:
    """Recalculates the total of an order based on its active items and updates it."""
    total = (
        db.query(func.sum(OrderItem.quantity * OrderItem.price))
        .filter(OrderItem.order_id == order_id)
        .scalar()
    )
    final_total = float(total or 0)
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")
    order.total = final_total
    return final_total


def get_open_cash_session(db: Session) -> CashSession | None:
    """Returns the currently active open cash session, if any."""
    return db.query(CashSession).filter(CashSession.status == "ABERTO").first()
