from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.cash_flow import CashFlow
from models.order_items import OrderItem
from models.orders import Order
from models.product import Product
from models.user import User
from utils.security import (
    get_current_user,
    get_db,
    get_open_cash_session,
    require_roles,
)

router = APIRouter(tags=["Relatórios & Dashboard"])


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    today = date.today()
    session = get_open_cash_session(db)

    orders_today = db.query(Order).filter(func.date(Order.created_at) == today).all()

    closed_today = [o for o in orders_today if o.status == "FECHADO"]
    open_now = [o for o in orders_today if o.status == "ABERTO"]
    total_today = sum(o.total for o in closed_today)

    pending_invoices = (
        db.query(Order)
        .filter(Order.payment_status == "PENDENTE", Order.payment_method == "FATURADO")
        .all()
    )
    total_fiado = sum(o.total for o in pending_invoices)

    cash_balance = None
    if session:
        movements = db.query(CashFlow).filter(CashFlow.cash_session_id == session.id).all()
        cash_balance = (
            session.opening_amount
            + sum(m.amount for m in movements if m.type == "ENTRADA")
            - sum(abs(m.amount) for m in movements if m.type in ["SANGRIA", "SAIDA", "RETIRADA"])
        )

    return {
        "total_today": total_today,
        "orders_closed_today": len(closed_today),
        "orders_open_now": len(open_now),
        "total_fiado_pendente": total_fiado,
        "cash_open": session is not None,
        "cash_balance": cash_balance,
    }


@router.get("/reports/period")
def period_report(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})
    movements = (
        db.query(CashFlow)
        .filter(
            func.date(CashFlow.created_at) >= start_date,
            func.date(CashFlow.created_at) <= end_date,
        )
        .all()
    )

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
        "items": len(movements),
    }


@router.get("/reports/products")
def products_report(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})

    orders = (
        db.query(Order)
        .filter(
            func.date(Order.created_at) >= start_date,
            func.date(Order.created_at) <= end_date,
            Order.status == "FECHADO",
        )
        .all()
    )

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
                "total": 0.0,
            }

        product_stats[pid]["quantity"] += item.quantity
        product_stats[pid]["total"] += item.quantity * item.price

    result = list(product_stats.values())
    result.sort(key=lambda x: x["quantity"], reverse=True)
    return result


@router.get("/reports/daily")
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
    return {
        "date": report_date,
        "total": total,
        "by_method": by_method,
        "items": len(movements),
    }
