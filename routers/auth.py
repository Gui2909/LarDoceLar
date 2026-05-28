from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.user import User
from models.user_session import UserSession
from utils.security import get_db, get_current_user, verify_password

router = APIRouter(prefix="/auth", tags=["Autenticação"])


class LoginRequest(BaseModel):
    name: str
    password: str


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    current_user = db.query(User).filter(User.name == data.name).first()
    if current_user is None or not verify_password(data.password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciais invalidas")

    token = str(uuid4())
    new_session = UserSession(token=token, user_id=current_user.id)
    db.add(new_session)
    db.commit()
    return {"token": token, "user_id": current_user.id, "role": current_user.role}


@router.get("/me")
def auth_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "name": current_user.name, "role": current_user.role}
