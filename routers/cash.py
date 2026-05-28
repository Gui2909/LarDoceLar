from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.cash_flow import CashFlow
from models.cash_session import CashSession
from models.orders import Order
from models.user import User
from utils.security import (
    get_current_user,
    get_db,
    get_open_cash_session,
    require_roles,
    verify_password,
)

router = APIRouter(prefix="", tags=["Controle de Caixa"])


class CashOpenRequest(BaseModel):
    opening_amount: float = Field(ge=0)


class CashCloseRequest(BaseModel):
    closing_amount: float = Field(ge=0)
    password: str | None = None


class CashMovementRequest(BaseModel):
    amount: float = Field(gt=0)
    description: str = Field(min_length=3, max_length=200)


@router.get("/cash/status")
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


@router.get("/cash/report")
def cash_report(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_roles(current_user, {"admin", "cashier"})
    session = get_open_cash_session(db)
    if session is None:
        raise HTTPException(status_code=400, detail="Caixa fechado")

    movements = db.query(CashFlow).filter(CashFlow.cash_session_id == session.id).all()

    report = {"expected_amount": session.opening_amount, "by_method": {}}

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


@router.get("/cashflow")
def list_cashflow(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_roles(current_user, {"admin"})
    return db.query(CashFlow).order_by(CashFlow.id.desc()).all()


@router.post("/cash/open")
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


@router.post("/cash/close")
def close_cash(
    data: CashCloseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})

    if not data.password:
        raise HTTPException(
            status_code=403,
            detail="Senha de administrador é obrigatória para fechar o caixa.",
        )

    admins = db.query(User).filter(User.role == "admin").all()
    verified_admin = None
    for admin in admins:
        if verify_password(data.password, admin.password_hash):
            verified_admin = admin
            break

    if not verified_admin:
        raise HTTPException(status_code=403, detail="Senha de administrador incorreta!")

    current_open = get_open_cash_session(db)
    if current_open is None:
        raise HTTPException(status_code=400, detail="Nao ha caixa aberto")

    open_orders = (
        db.query(Order)
        .filter(Order.status == "ABERTO", Order.cash_session_id == current_open.id)
        .all()
    )

    for o in open_orders:
        o.status = "FECHADO"
        o.payment_method = "FATURADO"
        o.payment_status = "PENDENTE"

    expected_amount = sum(
        movement.amount
        for movement in db.query(CashFlow)
        .filter(CashFlow.cash_session_id == current_open.id)
        .all()
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


@router.post("/cash/supply")
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


@router.post("/cash/withdrawal")
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
