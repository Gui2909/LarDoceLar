from datetime import date, datetime
from hashlib import sha256
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.connection import Base, SessionLocal, engine
from models.cash_session import CashSession
from models.cash_flow import CashFlow
from models.estoque import Estoque
from models.order_items import OrderItem
from models.orders import Order
from models.product import Product
from models.user import User

app = FastAPI(title="LarDoceLar PDV")
Base.metadata.create_all(bind=engine)


TOKENS: dict[str, int] = {}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_hash(password: str) -> str:
    return sha256(password.encode("utf-8")).hexdigest()


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


class CheckoutRequest(BaseModel):
    payment_method: str
    amount_received: float = Field(gt=0)


class CashOpenRequest(BaseModel):
    opening_amount: float = Field(ge=0)


class CashCloseRequest(BaseModel):
    closing_amount: float = Field(ge=0)


class CashMovementRequest(BaseModel):
    amount: float = Field(gt=0)
    description: str = Field(min_length=3, max_length=200)


class StockMovementRequest(BaseModel):
    quantity: int = Field(gt=0)


class StockAdjustRequest(BaseModel):
    quantity: int = Field(ge=0)


class AuditRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=200)


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


@app.post("/orders")
def create_order(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_roles(current_user, {"admin", "cashier"})
    new_order = Order(status="ABERTO", total=0)
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
    query = db.query(Order)
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
    return {
        "id": current.id,
        "status": current.status,
        "total": current.total,
        "items": items,
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

    total = recalculate_order_total(db, order_id)
    if data.amount_received < total:
        raise HTTPException(status_code=400, detail="Valor recebido menor que o total")

    items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    for item in items:
        stock = db.query(Estoque).filter(Estoque.product_id == item.product_id).first()
        if stock is None or stock.quantity < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Estoque insuficiente para produto {item.product_id}",
            )
    for item in items:
        stock = db.query(Estoque).filter(Estoque.product_id == item.product_id).first()
        stock.quantity -= item.quantity

    current_order.status = "FECHADO"
    db.add(
        CashFlow(
            order_id=current_order.id,
            cash_session_id=session.id,
            type="ENTRADA",
            amount=total,
            description=f"Venda pedido {current_order.id} (sessao {session.id})",
            payment_method=data.payment_method.upper(),
        )
    )
    db.commit()
    return {"message": "Pedido fechado", "total": total, "troco": data.amount_received - total}


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
    require_roles(current_user, {"admin"})
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
    require_roles(current_user, {"admin"})
    current_open = get_open_cash_session(db)
    if current_open is None:
        raise HTTPException(status_code=400, detail="Nao ha caixa aberto")

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


@app.post("/stock/{product_id}/in")
def stock_in(
    product_id: int,
    data: StockMovementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})
    product_exists = db.query(Product).filter(Product.id == product_id).first()
    if product_exists is None:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    stock = db.query(Estoque).filter(Estoque.product_id == product_id).first()
    if stock is None:
        stock = Estoque(product_id=product_id, quantity=0)
        db.add(stock)
    stock.quantity += data.quantity
    db.commit()
    return {"product_id": product_id, "quantity": stock.quantity}


@app.post("/stock/{product_id}/out")
def stock_out(
    product_id: int,
    data: StockMovementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})
    stock = db.query(Estoque).filter(Estoque.product_id == product_id).first()
    if stock is None:
        raise HTTPException(status_code=404, detail="Estoque nao encontrado")
    if stock.quantity < data.quantity:
        raise HTTPException(status_code=400, detail="Estoque insuficiente")
    stock.quantity -= data.quantity
    db.commit()
    return {"product_id": product_id, "quantity": stock.quantity}


@app.put("/stock/{product_id}/adjust")
def stock_adjust(
    product_id: int,
    data: StockAdjustRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})
    product_exists = db.query(Product).filter(Product.id == product_id).first()
    if product_exists is None:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    stock = db.query(Estoque).filter(Estoque.product_id == product_id).first()
    if stock is None:
        stock = Estoque(product_id=product_id, quantity=0)
        db.add(stock)
    stock.quantity = data.quantity
    db.commit()
    return {"product_id": product_id, "quantity": stock.quantity}


@app.get("/stock/low")
def low_stock(
    limit: int = Query(default=5, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    items = (
        db.query(Estoque, Product)
        .join(Product, Product.id == Estoque.product_id)
        .filter(Estoque.quantity <= limit, Product.is_active.is_(True))
        .all()
    )
    return [
        {
            "product_id": stock.product_id,
            "product_name": prod.name,
            "quantity": stock.quantity,
            "limit": limit,
        }
        for stock, prod in items
    ]


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
