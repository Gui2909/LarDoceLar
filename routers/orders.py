import os
import subprocess
import tempfile
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
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
    recalculate_order_total,
    require_roles,
    verify_password,
)

router = APIRouter(prefix="/orders", tags=["Pedidos"])


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


class PrintRequest(BaseModel):
    troco: float = 0.0
    payments: list[PaymentAmount] = []


class AuditRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=200)


class UserAuthRequest(BaseModel):
    password: str = Field(..., min_length=1)


class OrderDiscountRequest(BaseModel):
    discount: float = Field(ge=0)


class OrderNotesRequest(BaseModel):
    notes: str = Field(max_length=500)


@router.post("")
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    session = get_open_cash_session(db)
    session_id = session.id if session else None
    new_order = Order(
        status="ABERTO",
        total=0,
        customer_name=data.customer_name,
        cash_session_id=session_id,
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return new_order


@router.get("")
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
    orders = query.order_by(Order.id.desc()).all()
    return [
        {
            "id": o.id,
            "customer_name": o.customer_name,
            "status": o.status,
            "total": o.total,
            "payment_method": o.payment_method,
            "payment_status": o.payment_status,
            "created_at": o.created_at,
            "discount": getattr(o, "discount", None) or 0,
            "notes": getattr(o, "notes", None) or "",
        }
        for o in orders
    ]


@router.get("/{order_id}")
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
        flow = (
            db.query(CashFlow)
            .filter(
                CashFlow.type == "AUDITORIA",
                CashFlow.description.like(f"Cancelamento do pedido {order_id}%"),
            )
            .first()
        )
        if flow and "Motivo:" in flow.description:
            cancel_reason = flow.description.split("Motivo:")[-1].strip()

    items_data = []
    for item in items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        items_data.append(
            {
                "id": item.id,
                "order_id": item.order_id,
                "product_id": item.product_id,
                "product_name": product.name if product else "Produto Removido",
                "quantity": item.quantity,
                "price": item.price,
                "subtotal": item.quantity * item.price,
            }
        )

    return {
        "id": current.id,
        "customer_name": current.customer_name,
        "status": current.status,
        "total": current.total,
        "discount": getattr(current, "discount", None) or 0,
        "notes": getattr(current, "notes", None) or "",
        "items": items_data,
        "cancel_reason": cancel_reason,
    }


@router.post("/{order_id}/items")
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


@router.put("/{order_id}/items/{item_id}")
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


@router.delete("/{order_id}/items/{item_id}")
def remove_item(
    order_id: int,
    item_id: int,
    data: UserAuthRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})

    if not verify_password(data.password, current_user.password_hash):
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


@router.post("/{order_id}/checkout")
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
    discount = float(getattr(current_order, "discount", None) or 0)
    total = max(0.0, round(base_total - discount, 2))
    current_order.total = total
    total_received = sum(p.amount for p in data.payments)

    if round(total_received, 2) < round(total, 2):
        raise HTTPException(status_code=400, detail="Valor recebido menor que o total")

    current_order.status = "FECHADO"

    methods_used = [p.method.upper() for p in data.payments]
    if len(methods_used) > 1:
        current_order.payment_method = "MÚLTIPLO"
    elif len(methods_used) == 1:
        current_order.payment_method = methods_used[0]
    else:
        current_order.payment_method = "NAO_INFORMADO"

    if "FATURADO" in methods_used:
        current_order.payment_status = "PENDENTE"
    else:
        current_order.payment_status = "PAGO"

    for p in data.payments:
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


@router.post("/{order_id}/cancel")
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


@router.post("/{order_id}/print")
def print_order(
    order_id: int,
    data: PrintRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import os
    PRINTER_IP = os.getenv("PRINTER_IP", "192.168.5.98")
    try:
        PRINTER_PORT = int(os.getenv("PRINTER_PORT", "9100"))
    except ValueError:
        PRINTER_PORT = 9100
    COMPANY_NAME = os.getenv("COMPANY_NAME", "LarDoceLar")

    require_roles(current_user, {"admin", "cashier"})
    current_order = db.query(Order).filter(Order.id == order_id).first()
    if current_order is None:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")

    items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()

    lines = []
    lines.append("\x1b\x40")
    lines.append(f"{COMPANY_NAME.upper():^32}")
    lines.append("        Cupom nao Fiscal        ")
    lines.append("--------------------------------")
    lines.append(f"Pedido: #{current_order.id}")
    lines.append(f"Cliente: {current_order.customer_name or '—'}")

    created_val = current_order.created_at
    if isinstance(created_val, datetime):
        date_str = created_val.strftime("%d/%m/%Y %H:%M:%S")
    else:
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    lines.append(f"Data: {date_str}")
    lines.append("--------------------------------")
    lines.append("Item              Qtd    Total  ")
    lines.append("--------------------------------")

    for item in items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        product_name = product.name if product else "Produto Removido"
        name = product_name[:17]
        qty = str(item.quantity)
        item_subtotal = item.quantity * item.price
        price_total = f"{item_subtotal:.2f}"
        lines.append(f"{name:<18} {qty:>3} {price_total:>9}")

    lines.append("--------------------------------")

    subtotal = sum(item.quantity * item.price for item in items)
    lines.append(f"Subtotal:            R$ {subtotal:>10.2f}")

    discount = float(getattr(current_order, "discount", 0.0) or 0.0)
    if discount > 0:
        lines.append(f"Desconto:            R$ {discount:>10.2f}")

    lines.append(f"TOTAL:               R$ {current_order.total:>10.2f}")
    lines.append("--------------------------------")

    if data.payments:
        lines.append("Pagamento:")
        for p in data.payments:
            friendly_method = p.method.replace("_", " ").lower().title()
            lines.append(f" {friendly_method:<17}  R$ {p.amount:>10.2f}")
    else:
        method = current_order.payment_method or "Nao informado"
        friendly_method = method.replace("_", " ").lower().title()
        lines.append(f"Pagamento: {friendly_method}")

    if data.troco > 0:
        lines.append(f"Troco:               R$ {data.troco:>10.2f}")

    if current_order.notes:
        lines.append("--------------------------------")
        lines.append(f"Obs: {current_order.notes}")

    lines.append("--------------------------------")
    lines.append("    Obrigado pela preferencia!  ")
    lines.append("\n\n\n\n\n\x1bd\x01")

    ticket = "\n".join(lines)
    errors = []

    try:
        with open("print_debug.log", "a", encoding="utf-8") as f_debug:
            f_debug.write(f"[{datetime.now()}] --- PRINT ORDER REQUESTED (Order #{order_id}) ---\n")
    except Exception:
        pass

    try:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5.0)
            s.connect((PRINTER_IP, PRINTER_PORT))
            s.sendall(ticket.encode("cp860", errors="ignore"))
        try:
            with open("print_debug.log", "a", encoding="utf-8") as f_debug:
                f_debug.write(f"[{datetime.now()}] Method 0 (Socket TCP) SUCCESS\n")
        except Exception:
            pass
        return {"status": "success", "method": f"network socket ({PRINTER_IP}:{PRINTER_PORT})"}
    except Exception as e:
        try:
            with open("print_debug.log", "a", encoding="utf-8") as f_debug:
                f_debug.write(f"[{datetime.now()}] Method 0 (Socket TCP) FAILED: {str(e)}\n")
        except Exception:
            pass
        errors.append(f"socket network {PRINTER_IP}:{PRINTER_PORT}: {str(e)}")

    for port in [
        r"\\localhost\imp",
        r"\\127.0.0.1\imp",
        "imp",
        r"\\localhost\IMP",
        r"\\127.0.0.1\IMP",
        "IMP",
    ]:
        try:
            with open(port, "wb") as f:
                f.write(ticket.encode("cp860", errors="ignore"))
            try:
                with open("print_debug.log", "a", encoding="utf-8") as f_debug:
                    f_debug.write(f"[{datetime.now()}] Method 1 (Direct Open: {port}) SUCCESS\n")
            except Exception:
                pass
            return {"status": "success", "method": f"direct ({port})"}
        except Exception as e:
            try:
                with open("print_debug.log", "a", encoding="utf-8") as f_debug:
                    f_debug.write(f"[{datetime.now()}] Method 1 (Direct Open: {port}) FAILED: {str(e)}\n")
            except Exception:
                pass
            errors.append(f"direct {port}: {str(e)}")

    try:
        temp_fd, temp_path = tempfile.mkstemp(suffix=".txt")
        try:
            with os.fdopen(temp_fd, "wb") as tmp:
                tmp.write(ticket.encode("cp860", errors="ignore"))

            for print_cmd in [
                ["cmd", "/c", f"copy /B {temp_path} \\\\127.0.0.1\\imp"],
                ["cmd", "/c", f"copy /B {temp_path} \\\\localhost\\imp"],
                ["cmd", "/c", f"copy /B {temp_path} imp"],
                ["cmd", "/c", f"print /D:imp {temp_path}"],
                ["cmd", "/c", f"copy /B {temp_path} \\\\127.0.0.1\\IMP"],
                ["cmd", "/c", f"copy /B {temp_path} \\\\localhost\\IMP"],
                ["cmd", "/c", f"copy /B {temp_path} IMP"],
                ["cmd", "/c", f"print /D:IMP {temp_path}"],
            ]:
                try:
                    subprocess.run(
                        print_cmd,
                        shell=True,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    try:
                        with open("print_debug.log", "a", encoding="utf-8") as f_debug:
                            f_debug.write(f"[{datetime.now()}] Method 2 (CMD: {' '.join(print_cmd)}) SUCCESS\n")
                    except Exception:
                        pass
                    return {"status": "success", "method": f"cmd ({' '.join(print_cmd)})"}
                except Exception as e:
                    try:
                        with open("print_debug.log", "a", encoding="utf-8") as f_debug:
                            f_debug.write(f"[{datetime.now()}] Method 2 (CMD: {' '.join(print_cmd)}) FAILED: {str(e)}\n")
                    except Exception:
                        pass
                    errors.append(f"cmd {' '.join(print_cmd)}: {str(e)}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except Exception as e:
        errors.append(f"tempfile: {str(e)}")

    raise HTTPException(
        status_code=500,
        detail=f"Erro ao imprimir na impressora 'IMP'. Verifique se ela foi compartilhada na rede com esse nome exato. Detalhes: {'; '.join(errors)}",
    )


@router.delete("/{order_id}")
def delete_order(
    order_id: int,
    data: UserAuthRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})

    if not verify_password(data.password, current_user.password_hash):
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


@router.put("/{order_id}/discount")
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


@router.put("/{order_id}/notes")
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
