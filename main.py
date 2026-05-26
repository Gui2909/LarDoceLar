from datetime import date, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.connection import Base, SessionLocal, engine
from models.cash_session import CashSession
from models.cash_flow import CashFlow
from models.order_items import OrderItem
from models.orders import Order
from models.product import Product
from models.user import User

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="LarDoceLar PDV")

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def serve_frontend():
    return FileResponse("frontend/index.html")

Base.metadata.create_all(bind=engine)


def run_migrations():
    """Safe migrations: add columns that may not exist yet."""
    from sqlalchemy import text
    with engine.connect() as conn:
        migrations = [
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS discount FLOAT DEFAULT 0",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS notes VARCHAR",
        ]
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                conn.rollback()

run_migrations()


TOKENS: dict[str, int] = {}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_hash(password: str) -> str:
    return sha256(password.encode("utf-8")).hexdigest()

def create_initial_admin():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.name == "Lygio").first()
        if not admin:
            new_admin = User(
                name="Lygio",
                password_hash=make_hash("142536"),
                role="admin"
            )
            db.add(new_admin)
            db.commit()
    except Exception as e:
        print(f"Erro ao criar admin inicial: {e}")
    finally:
        db.close()

create_initial_admin()


def recalculate_order_total(db: Session, order_id: int) -> float:
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
    return db.query(CashSession).filter(CashSession.status == "ABERTO").first()


def get_current_user(
    db: Session = Depends(get_db),
    x_token: str | None = Header(default=None),
):
    if not x_token:
        raise HTTPException(status_code=401, detail="Token ausente")
    user_id = TOKENS.get(x_token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token invalido")
    current_user = db.query(User).filter(User.id == user_id).first()
    if current_user is None:
        raise HTTPException(status_code=401, detail="Usuario do token nao encontrado")
    return current_user


def require_roles(current_user: User, roles: set[str]):
    if current_user.role.lower() not in roles:
        raise HTTPException(status_code=403, detail="Sem permissao para esta operacao")


class UserCreate(BaseModel):
    name: str = Field(min_length=3, max_length=50)
    role: str = Field(default="cashier")
    password: str = Field(min_length=4)


class LoginRequest(BaseModel):
    name: str
    password: str


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    category: str | None = None
    price: float = Field(gt=0)


class ProductUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    category: str | None = None
    price: float = Field(gt=0)
    is_active: bool = True


class AddItemRequest(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class UpdateItemRequest(BaseModel):
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    customer_name: str

class PaymentAmount(BaseModel):
    method: str
    amount: float = Field(gt=0)

class CheckoutRequest(BaseModel):
    payments: list[PaymentAmount]


class CashOpenRequest(BaseModel):
    opening_amount: float = Field(ge=0)


class CashCloseRequest(BaseModel):
    closing_amount: float = Field(ge=0)
    password: str | None = None

class PayInvoiceRequest(BaseModel):
    payment_method: str


class CashMovementRequest(BaseModel):
    amount: float = Field(gt=0)
    description: str = Field(min_length=3, max_length=200)


class StockMovementRequest(BaseModel):
    quantity: int = Field(gt=0)


class StockAdjustRequest(BaseModel):
    quantity: int = Field(ge=0)


class AuditRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=200)

class UserAuthRequest(BaseModel):
    password: str = Field(..., min_length=1)

class OrderDiscountRequest(BaseModel):
    discount: float = Field(ge=0)

class OrderNotesRequest(BaseModel):
    notes: str = Field(max_length=500)

@app.get("/users")
def list_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_roles(current_user, {"admin"})
    users = db.query(User).all()
    return [{"id": u.id, "name": u.name, "role": u.role} for u in users]


@app.post("/users")
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    x_token: str | None = Header(default=None),
):
    has_users = db.query(User).count() > 0
    if has_users:
        if not x_token:
            raise HTTPException(status_code=401, detail="Token ausente")
        user_id = TOKENS.get(x_token)
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token invalido")
        current_user = db.query(User).filter(User.id == user_id).first()
        if current_user is None:
            raise HTTPException(status_code=401, detail="Usuario do token nao encontrado")
        require_roles(current_user, {"admin"})
    else:
        data.role = "admin"

    existing = db.query(User).filter(User.name == data.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Usuario ja existe")

    new_user = User(
        name=data.name,
        role=data.role,
        password_hash=make_hash(data.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"id": new_user.id, "name": new_user.name, "role": new_user.role}


@app.post("/auth/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    current_user = db.query(User).filter(User.name == data.name).first()
    if current_user is None or current_user.password_hash != make_hash(data.password):
        raise HTTPException(status_code=401, detail="Credenciais invalidas")

    token = str(uuid4())
    TOKENS[token] = current_user.id
    return {"token": token, "user_id": current_user.id, "role": current_user.role}


@app.get("/auth/me")
def auth_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "name": current_user.name, "role": current_user.role}


@app.post("/products")
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})
    existing = db.query(Product).filter(Product.name == data.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Produto ja existe")

    new_product = Product(name=data.name, category=data.category, price=data.price)
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product


@app.get("/products")
def list_products(only_active: bool = True, db: Session = Depends(get_db)):
    query = db.query(Product)
    if only_active:
        query = query.filter(Product.is_active.is_(True))
    return query.all()


@app.put("/products/{product_id}")
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})
    current = db.query(Product).filter(Product.id == product_id).first()
    if current is None:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    current.name = data.name
    current.category = data.category
    current.price = data.price
    current.is_active = data.is_active
    db.commit()
    db.refresh(current)
    return current


@app.post("/products/{product_id}/deactivate")
def deactivate_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})
    current = db.query(Product).filter(Product.id == product_id).first()
    if current is None:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    current.is_active = False
    db.commit()
    return {"message": "Produto inativado"}


@app.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    data: UserAuthRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})
    
    if current_user.password_hash != make_hash(data.password):
        raise HTTPException(status_code=403, detail="Senha incorreta!")
        
    current = db.query(Product).filter(Product.id == product_id).first()
    if current is None:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
        
    db.delete(current)
    db.commit()
    return {"message": "Produto excluido"}


@app.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    data: UserAuthRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})
    
    if current_user.password_hash != make_hash(data.password):
        raise HTTPException(status_code=403, detail="Senha incorreta!")
        
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Nao pode excluir o proprio usuario")
        
    current = db.query(User).filter(User.id == user_id).first()
    if current is None:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
        
    db.delete(current)
    db.commit()
    return {"message": "Usuario excluido"}


@app.post("/orders")
def create_order(data: OrderCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_roles(current_user, {"admin", "cashier"})
    session = get_open_cash_session(db)
    session_id = session.id if session else None
    new_order = Order(status="ABERTO", total=0, customer_name=data.customer_name, cash_session_id=session_id)
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return new_order


@app.get("/orders")
def list_orders(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    session = get_open_cash_session(db)
    if not session:
        return []
    query = db.query(Order).filter(Order.cash_session_id == session.id)
    if status:
        query = query.filter(Order.status == status.upper())
    return query.order_by(Order.id.desc()).all()


@app.get("/orders/{order_id}")
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    current = db.query(Order).filter(Order.id == order_id).first()
    if current is None:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")
    items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    
    cancel_reason = None
    if current.status == "CANCELADO":
        flow = db.query(CashFlow).filter(CashFlow.type == "AUDITORIA", CashFlow.description.like(f"Cancelamento do pedido {order_id}%")).first()
        if flow and "Motivo:" in flow.description:
            cancel_reason = flow.description.split("Motivo:")[-1].strip()

    items_data = []
    for item in items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        items_data.append({
            "id": item.id,
            "order_id": item.order_id,
            "product_id": item.product_id,
            "product_name": product.name if product else "Produto Removido",
            "quantity": item.quantity,
            "price": item.price,
            "subtotal": item.quantity * item.price
        })

    return {
        "id": current.id,
        "customer_name": current.customer_name,
        "status": current.status,
        "total": current.total,
        "discount": current.discount or 0,
        "notes": current.notes or "",
        "items": items_data,
        "cancel_reason": cancel_reason,
    }


@app.post("/orders/{order_id}/items")
def add_item(
    order_id: int,
    data: AddItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    current_order = db.query(Order).filter(Order.id == order_id).first()
    if current_order is None:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")
    if current_order.status != "ABERTO":
        raise HTTPException(status_code=400, detail="Pedido nao esta aberto")

    current_product = db.query(Product).filter(Product.id == data.product_id).first()
    if current_product is None or not current_product.is_active:
        raise HTTPException(status_code=404, detail="Produto indisponivel")

    item = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order_id, OrderItem.product_id == data.product_id)
        .first()
    )
    if item:
        item.quantity += data.quantity
    else:
        item = OrderItem(
            order_id=order_id,
            product_id=data.product_id,
            quantity=data.quantity,
            price=current_product.price,
        )
        db.add(item)

    recalculate_order_total(db, order_id)
    db.commit()
    return {"message": "Item adicionado"}


@app.put("/orders/{order_id}/items/{item_id}")
def update_item(
    order_id: int,
    item_id: int,
    data: UpdateItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    current_order = db.query(Order).filter(Order.id == order_id).first()
    if current_order is None:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")
    if current_order.status != "ABERTO":
        raise HTTPException(status_code=400, detail="Pedido nao esta aberto")

    item = (
        db.query(OrderItem)
        .filter(OrderItem.id == item_id, OrderItem.order_id == order_id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Item nao encontrado")

    item.quantity = data.quantity
    recalculate_order_total(db, order_id)
    db.commit()
    return {"message": "Item atualizado"}


@app.delete("/orders/{order_id}/items/{item_id}")
def remove_item(
    order_id: int,
    item_id: int,
    data: UserAuthRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    
    if current_user.password_hash != make_hash(data.password):
        raise HTTPException(status_code=403, detail="Senha incorreta!")
        
    current_order = db.query(Order).filter(Order.id == order_id).first()
    if current_order is None:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")
    if current_order.status != "ABERTO":
        raise HTTPException(status_code=400, detail="Pedido nao esta aberto")

    item = (
        db.query(OrderItem)
        .filter(OrderItem.id == item_id, OrderItem.order_id == order_id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Item nao encontrado")

    db.delete(item)
    recalculate_order_total(db, order_id)
    db.commit()
    return {"message": "Item removido"}


@app.post("/orders/{order_id}/checkout")
def checkout_order(
    order_id: int,
    data: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    current_order = db.query(Order).filter(Order.id == order_id).first()
    if current_order is None:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")
    if current_order.status != "ABERTO":
        raise HTTPException(status_code=400, detail="Pedido nao esta aberto")

    items_count = db.query(OrderItem).filter(OrderItem.order_id == order_id).count()
    if items_count == 0:
        raise HTTPException(status_code=400, detail="Pedido vazio")

    session = get_open_cash_session(db)
    if session is None:
        raise HTTPException(status_code=400, detail="Caixa fechado. Abra o caixa antes do checkout")

    base_total = recalculate_order_total(db, order_id)
    discount = float(current_order.discount or 0)
    total = max(0.0, round(base_total - discount, 2))
    current_order.total = total
    total_received = sum(p.amount for p in data.payments)
    
    if round(total_received, 2) < round(total, 2):
        raise HTTPException(status_code=400, detail="Valor recebido menor que o total")

    items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()

    current_order.status = "FECHADO"
    
    # Check if Faturado is used
    methods_used = [p.method.upper() for p in data.payments]
    if len(methods_used) > 1:
        current_order.payment_method = "MÚLTIPLO"
    elif len(methods_used) == 1:
        current_order.payment_method = methods_used[0]
    else:
        current_order.payment_method = "NAO_INFORMADO"

    if "FATURADO" in methods_used:
        # If FATURADO is mixed, we consider it PENDENTE until fully paid later.
        # But realistically we just set the overall order payment_status to PENDENTE if FATURADO is used.
        current_order.payment_status = "PENDENTE"
    else:
        current_order.payment_status = "PAGO"
        
    for p in data.payments:
        # Do not add CashFlow for FATURADO directly as it's not physical money entering yet.
        if p.method.upper() != "FATURADO":
            db.add(
                CashFlow(
                    order_id=current_order.id,
                    cash_session_id=session.id,
                    type="ENTRADA",
                    amount=p.amount,
                    description=f"Venda pedido {current_order.id} (sessao {session.id})",
                    payment_method=p.method.upper(),
                )
            )
            
    db.commit()
    return {"message": "Pedido fechado", "total": total, "troco": total_received - total}


@app.post("/orders/{order_id}/cancel")
def cancel_order(
    order_id: int,
    data: AuditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})
    current_order = db.query(Order).filter(Order.id == order_id).first()
    if current_order is None:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")
    if current_order.status != "ABERTO":
        raise HTTPException(status_code=400, detail="Apenas pedido aberto pode ser cancelado")

    current_order.status = "CANCELADO"
    db.add(
        CashFlow(
            type="AUDITORIA",
            amount=0,
            description=(
                f"Cancelamento do pedido {order_id} por usuario {current_user.id}. "
                f"Motivo: {data.reason}"
            ),
            payment_method="NA",
        )
    )
    db.commit()
    return {"message": "Pedido cancelado"}


@app.delete("/orders/{order_id}")
def delete_order(
    order_id: int,
    data: UserAuthRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    
    if current_user.password_hash != make_hash(data.password):
        raise HTTPException(status_code=403, detail="Senha incorreta!")
        
    current_order = db.query(Order).filter(Order.id == order_id).first()
    if current_order is None:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")

    db.query(CashFlow).filter(CashFlow.order_id == order_id).delete()
    db.query(OrderItem).filter(OrderItem.order_id == order_id).delete()
    db.delete(current_order)
    
    db.add(
        CashFlow(
            type="AUDITORIA",
            amount=0,
            description=(
                f"Exclusao do pedido {order_id} (Cliente: {current_order.customer_name}) por usuario {current_user.id}."
            ),
            payment_method="NA",
        )
    )
    
    db.commit()
    return {"message": "Pedido excluido"}


@app.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    today = date.today()
    session = get_open_cash_session(db)

    # Pedidos de hoje
    orders_today = db.query(Order).filter(
        func.date(Order.created_at) == today
    ).all()

    closed_today = [o for o in orders_today if o.status == "FECHADO"]
    open_now = [o for o in orders_today if o.status == "ABERTO"]
    total_today = sum(o.total for o in closed_today)

    # Fiado pendente total
    pending_invoices = db.query(Order).filter(
        Order.payment_status == "PENDENTE",
        Order.payment_method == "FATURADO"
    ).all()
    total_fiado = sum(o.total for o in pending_invoices)

    # Caixa
    cash_balance = None
    if session:
        movements = db.query(CashFlow).filter(CashFlow.cash_session_id == session.id).all()
        cash_balance = session.opening_amount + sum(
            m.amount for m in movements if m.type == "ENTRADA"
        ) - sum(
            abs(m.amount) for m in movements if m.type in ["SANGRIA", "SAIDA", "RETIRADA"]
        )

    return {
        "total_today": total_today,
        "orders_closed_today": len(closed_today),
        "orders_open_now": len(open_now),
        "total_fiado_pendente": total_fiado,
        "cash_open": session is not None,
        "cash_balance": cash_balance,
    }


@app.put("/orders/{order_id}/discount")
def set_discount(
    order_id: int,
    data: OrderDiscountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    current_order = db.query(Order).filter(Order.id == order_id).first()
    if current_order is None:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")
    if current_order.status != "ABERTO":
        raise HTTPException(status_code=400, detail="Pedido nao esta aberto")
    current_order.discount = data.discount
    db.commit()
    return {"message": "Desconto aplicado", "discount": data.discount}


@app.put("/orders/{order_id}/notes")
def set_notes(
    order_id: int,
    data: OrderNotesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    current_order = db.query(Order).filter(Order.id == order_id).first()
    if current_order is None:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")
    current_order.notes = data.notes
    db.commit()
    return {"message": "Observacao salva"}


@app.get("/cash/status")
def cash_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_roles(current_user, {"admin", "cashier"})
    session = get_open_cash_session(db)
    if session is None:
        return {"open": False, "session": None}
    movements = db.query(CashFlow).filter(CashFlow.cash_session_id == session.id).all()
    expected_amount = sum(m.amount for m in movements)
    return {
        "open": True,
        "session": {
            "id": session.id,
            "status": session.status,
            "opening_amount": session.opening_amount,
            "opened_at": session.opened_at,
            "expected_amount": expected_amount,
        },
    }


@app.get("/cash/report")
def cash_report(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_roles(current_user, {"admin", "cashier"})
    session = get_open_cash_session(db)
    if session is None:
        raise HTTPException(status_code=400, detail="Caixa fechado")
        
    movements = db.query(CashFlow).filter(CashFlow.cash_session_id == session.id).all()
    
    report = {
        "expected_amount": session.opening_amount,
        "by_method": {}
    }
    
    for m in movements:
        if m.type == "ENTRADA" or m.type == "ABERTURA":
            report["expected_amount"] += m.amount
            method = m.payment_method or "NAO_INFORMADO"
            report["by_method"][method] = report["by_method"].get(method, 0) + m.amount
        elif m.type in ["SAIDA", "RETIRADA", "SANGRIA"]:
            report["expected_amount"] -= m.amount
            method = m.payment_method or "NAO_INFORMADO"
            report["by_method"][method] = report["by_method"].get(method, 0) - m.amount

    return report


@app.get("/cashflow")
def list_cashflow(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_roles(current_user, {"admin"})
    return db.query(CashFlow).order_by(CashFlow.id.desc()).all()


@app.post("/cash/open")
def open_cash(
    data: CashOpenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    current_open = get_open_cash_session(db)
    if current_open is not None:
        raise HTTPException(status_code=409, detail="Ja existe caixa aberto")

    session = CashSession(status="ABERTO", opening_amount=data.opening_amount)
    db.add(session)
    db.flush()
    db.add(
        CashFlow(
            cash_session_id=session.id,
            type="ABERTURA",
            amount=data.opening_amount,
            description=f"Abertura de caixa sessao {session.id}",
            payment_method="DINHEIRO",
        )
    )
    db.commit()
    db.refresh(session)
    return session


@app.post("/cash/close")
def close_cash(
    data: CashCloseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    
    if not data.password:
        raise HTTPException(status_code=403, detail="Senha de administrador é obrigatória para fechar o caixa.")
        
    admin_user = db.query(User).filter(User.role == "admin", User.password_hash == make_hash(data.password)).first()
    if not admin_user:
        raise HTTPException(status_code=403, detail="Senha de administrador incorreta!")

    current_open = get_open_cash_session(db)
    if current_open is None:
        raise HTTPException(status_code=400, detail="Nao ha caixa aberto")

    open_orders = db.query(Order).filter(Order.status == "ABERTO", Order.cash_session_id == current_open.id).all()

    for o in open_orders:
        o.status = "FECHADO"
        o.payment_method = "FATURADO"
        o.payment_status = "PENDENTE"

    expected_amount = sum(
        movement.amount
        for movement in db.query(CashFlow).filter(CashFlow.cash_session_id == current_open.id).all()
    )
    difference = data.closing_amount - expected_amount

    current_open.status = "FECHADO"
    current_open.closing_amount = data.closing_amount
    current_open.closed_at = datetime.utcnow()
    db.add(
        CashFlow(
            cash_session_id=current_open.id,
            type="FECHAMENTO",
            amount=data.closing_amount,
            description=(
                f"Fechamento de caixa sessao {current_open.id}. "
                f"Esperado={expected_amount:.2f} Diferenca={difference:.2f}"
            ),
            payment_method="DINHEIRO",
        )
    )
    db.commit()
    return {
        "message": "Caixa fechado",
        "session_id": current_open.id,
        "expected_amount": expected_amount,
        "difference": difference,
    }


@app.post("/cash/supply")
def cash_supply(
    data: CashMovementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    current_open = get_open_cash_session(db)
    if current_open is None:
        raise HTTPException(status_code=400, detail="Nao ha caixa aberto")
    db.add(
        CashFlow(
            cash_session_id=current_open.id,
            type="SUPRIMENTO",
            amount=data.amount,
            description=f"Sessao {current_open.id}: {data.description}",
            payment_method="DINHEIRO",
        )
    )
    db.commit()
    return {"message": "Suprimento registrado"}


@app.post("/cash/withdrawal")
def cash_withdrawal(
    data: CashMovementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})
    current_open = get_open_cash_session(db)
    if current_open is None:
        raise HTTPException(status_code=400, detail="Nao ha caixa aberto")
    db.add(
        CashFlow(
            cash_session_id=current_open.id,
            type="SANGRIA",
            amount=-data.amount,
            description=f"Sessao {current_open.id}: {data.description}",
            payment_method="DINHEIRO",
        )
    )
    db.commit()
    return {"message": "Sangria registrada"}


@app.get("/invoices")
def list_invoices(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_roles(current_user, {"admin", "cashier"})
    pending_orders = db.query(Order).filter(
        Order.payment_status == "PENDENTE", 
        Order.payment_method == "FATURADO"
    ).all()
    
    invoices = {}
    for o in pending_orders:
        if not o.customer_name:
            continue
        if o.customer_name not in invoices:
            invoices[o.customer_name] = {
                "customer_name": o.customer_name,
                "first_purchase": o.created_at,
                "total": 0.0,
                "orders": []
            }
        else:
            if o.created_at < invoices[o.customer_name]["first_purchase"]:
                invoices[o.customer_name]["first_purchase"] = o.created_at
        
        invoices[o.customer_name]["total"] += o.total
        
        items = db.query(OrderItem).filter(OrderItem.order_id == o.id).all()
        order_items_data = []
        for i in items:
            p = db.query(Product).filter(Product.id == i.product_id).first()
            order_items_data.append({
                "product_name": p.name if p else "Removido",
                "quantity": i.quantity,
                "price": i.price,
                "subtotal": i.quantity * i.price
            })
            
        invoices[o.customer_name]["orders"].append({
            "id": o.id,
            "created_at": o.created_at,
            "total": o.total,
            "items": order_items_data
        })
        
    result = list(invoices.values())
    return result

@app.post("/invoices/{customer_name}/pay")
def pay_invoice(
    customer_name: str,
    data: PayInvoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_roles(current_user, {"admin", "cashier"})
    session = get_open_cash_session(db)
    if session is None:
        raise HTTPException(status_code=400, detail="Caixa fechado. Abra o caixa antes de quitar dívidas.")
        
    pending_orders = db.query(Order).filter(
        Order.payment_status == "PENDENTE",
        Order.payment_method == "FATURADO",
        Order.customer_name == customer_name
    ).all()
    
    if not pending_orders:
        raise HTTPException(status_code=404, detail="Nenhuma dívida encontrada para este cliente.")
        
    total_paid = sum(o.total for o in pending_orders)
    
    for o in pending_orders:
        o.payment_status = "PAGO"
        
    db.add(
        CashFlow(
            cash_session_id=session.id,
            type="ENTRADA",
            amount=total_paid,
            description=f"Quitação faturado: {customer_name}",
            payment_method=data.payment_method.upper(),
        )
    )
    
    db.commit()
    return {"message": "Dívida quitada com sucesso", "total": total_paid}


@app.get("/reports/period")
def period_report(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})
    movements = db.query(CashFlow).filter(
        func.date(CashFlow.created_at) >= start_date,
        func.date(CashFlow.created_at) <= end_date
    ).all()
    
    total = sum(m.amount for m in movements if m.type in ["ENTRADA", "ABERTURA"])
    by_method: dict[str, float] = {}
    for m in movements:
        if m.type in ["ENTRADA", "ABERTURA"]:
            method = m.payment_method or "NAO_INFORMADO"
            by_method[method] = by_method.get(method, 0) + m.amount
            
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total": total,
        "by_method": by_method,
        "items": len(movements)
    }


@app.get("/reports/products")
def products_report(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})
    
    # Get all closed orders in the period
    orders = db.query(Order).filter(
        func.date(Order.created_at) >= start_date,
        func.date(Order.created_at) <= end_date,
        Order.status == "FECHADO"
    ).all()
    
    order_ids = [o.id for o in orders]
    
    if not order_ids:
        return []
        
    items = db.query(OrderItem).filter(OrderItem.order_id.in_(order_ids)).all()
    
    product_stats = {}
    for item in items:
        pid = item.product_id
        if pid not in product_stats:
            p = db.query(Product).filter(Product.id == pid).first()
            product_stats[pid] = {
                "product_id": pid,
                "product_name": p.name if p else "Removido",
                "quantity": 0,
                "total": 0.0
            }
        
        product_stats[pid]["quantity"] += item.quantity
        product_stats[pid]["total"] += (item.quantity * item.price)
        
    # Sort by quantity descending
    result = list(product_stats.values())
    result.sort(key=lambda x: x["quantity"], reverse=True)
    return result


@app.get("/reports/daily")
def daily_report(
    report_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})
    movements = db.query(CashFlow).filter(func.date(CashFlow.created_at) == report_date).all()
    total = sum(m.amount for m in movements)
    by_method: dict[str, float] = {}
    for movement in movements:
        method = movement.payment_method or "NAO_INFORMADO"
        by_method[method] = by_method.get(method, 0) + movement.amount
    return {"date": report_date, "total": total, "by_method": by_method, "items": len(movements)}
