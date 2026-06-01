from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from database.connection import Base, SessionLocal, engine

from models.cash_flow import CashFlow
from models.cash_session import CashSession
from models.ingredient import Ingredient
from models.order_items import OrderItem
from models.orders import Order
from models.product import Product
from models.user import User
from models.user_session import UserSession
from routers import auth, cash, invoices, orders, products, reports, users
from utils.security import hash_password

app = FastAPI(title="LarDoceLar PDV")

app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def serve_frontend():
    return FileResponse("frontend/index.html")


@app.get("/api/config")
def serve_config():
    import os
    return {
        "company_name": os.getenv("COMPANY_NAME", "LarDoceLar"),
        "company_brand": os.getenv("COMPANY_BRAND", "Doce Lar"),
        "company_logo": os.getenv("COMPANY_LOGO", "/static/img/logo.png"),
        "printer_ip": os.getenv("PRINTER_IP", "192.168.5.98"),
        "printer_port": int(os.getenv("PRINTER_PORT", "9100"))
    }


Base.metadata.create_all(bind=engine)


def run_migrations():
    """Safe migrations: add new columns without breaking existing data."""
    try:
        migrations = [
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS discount FLOAT DEFAULT 0",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS notes VARCHAR",
        ]
        for sql in migrations:
            try:
                with engine.begin() as conn:
                    conn.execute(text(sql))
            except Exception:
                pass
    except Exception:
        pass


try:
    run_migrations()
except Exception:
    pass


def create_initial_admin():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.name == "Lygio").first()
        if not admin:
            new_admin = User(
                name="Lygio", password_hash=hash_password("142536"), role="admin"
            )
            db.add(new_admin)
            db.commit()
    except Exception as e:
        print(f"Erro ao criar admin inicial: {e}")
    finally:
        db.close()


create_initial_admin()

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(cash.router)
app.include_router(invoices.router)
app.include_router(reports.router)
