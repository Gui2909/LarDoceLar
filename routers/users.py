from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.user import User
from models.user_session import UserSession
from utils.security import (
    get_db,
    get_current_user,
    require_roles,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/users", tags=["Usuários"])


class UserCreate(BaseModel):
    name: str = Field(min_length=3, max_length=50)
    role: str = Field(default="cashier")
    password: str = Field(min_length=4)


class UserAuthRequest(BaseModel):
    password: str = Field(..., min_length=1)


@router.get("")
def list_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_roles(current_user, {"admin"})
    users = db.query(User).all()
    return [{"id": u.id, "name": u.name, "role": u.role} for u in users]


@router.post("")
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    x_token: str | None = Header(default=None),
):
    has_users = db.query(User).count() > 0
    if has_users:
        if not x_token:
            raise HTTPException(status_code=401, detail="Token ausente")
        session = db.query(UserSession).filter(UserSession.token == x_token).first()
        if session is None:
            raise HTTPException(status_code=401, detail="Token invalido")
        current_user = db.query(User).filter(User.id == session.user_id).first()
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
        password_hash=hash_password(data.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"id": new_user.id, "name": new_user.name, "role": new_user.role}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    data: UserAuthRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})

    if not verify_password(data.password, current_user.password_hash):
        raise HTTPException(status_code=403, detail="Senha incorreta!")

    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Nao pode excluir o proprio usuario")

    current = db.query(User).filter(User.id == user_id).first()
    if current is None:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    db.query(UserSession).filter(UserSession.user_id == user_id).delete()
    db.delete(current)
    db.commit()
    return {"message": "Usuario excluido"}
