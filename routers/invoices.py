from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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

router = APIRouter(prefix="/invoices", tags=["Fiados / Faturados"])


class PayInvoiceRequest(BaseModel):
    payment_method: str


@router.get("")
def list_invoices(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_roles(current_user, {"admin", "cashier"})
    pending_orders = (
        db.query(Order)
        .filter(Order.payment_status == "PENDENTE", Order.payment_method == "FATURADO")
        .all()
    )

    invoices = {}
    for o in pending_orders:
        if not o.customer_name:
            continue
        if o.customer_name not in invoices:
            invoices[o.customer_name] = {
                "customer_name": o.customer_name,
                "first_purchase": o.created_at,
                "total": 0.0,
                "orders": [],
            }
        else:
            if o.created_at < invoices[o.customer_name]["first_purchase"]:
                invoices[o.customer_name]["first_purchase"] = o.created_at

        invoices[o.customer_name]["total"] += o.total

        items = db.query(OrderItem).filter(OrderItem.order_id == o.id).all()
        order_items_data = []
        for i in items:
            p = db.query(Product).filter(Product.id == i.product_id).first()
            order_items_data.append(
                {
                    "product_name": p.name if p else "Removido",
                    "quantity": i.quantity,
                    "price": i.price,
                    "subtotal": i.quantity * i.price,
                }
            )

        invoices[o.customer_name]["orders"].append(
            {
                "id": o.id,
                "created_at": o.created_at,
                "total": o.total,
                "items": order_items_data,
            }
        )

    result = list(invoices.values())
    return result


@router.post("/{customer_name}/pay")
def pay_invoice(
    customer_name: str,
    data: PayInvoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    session = get_open_cash_session(db)
    if session is None:
        raise HTTPException(
            status_code=400,
            detail="Caixa fechado. Abra o caixa antes de quitar dívidas.",
        )

    pending_orders = (
        db.query(Order)
        .filter(
            Order.payment_status == "PENDENTE",
            Order.payment_method == "FATURADO",
            Order.customer_name == customer_name,
        )
        .all()
    )

    if not pending_orders:
        raise HTTPException(
            status_code=404,
            detail="Nenhuma dívida encontrada para este cliente.",
        )

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
