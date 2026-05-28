from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.product import Product
from models.user import User
from utils.security import (
    get_db,
    get_current_user,
    require_roles,
    verify_password,
)

router = APIRouter(prefix="/products", tags=["Produtos"])


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    category: str | None = None
    price: float = Field(gt=0)


class ProductUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    category: str | None = None
    price: float = Field(gt=0)
    is_active: bool = True


class UserAuthRequest(BaseModel):
    password: str = Field(..., min_length=1)


@router.post("")
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


@router.get("")
def list_products(only_active: bool = True, db: Session = Depends(get_db)):
    query = db.query(Product)
    if only_active:
        query = query.filter(Product.is_active.is_(True))
    return query.all()


@router.put("/{product_id}")
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


@router.post("/{product_id}/deactivate")
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


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    data: UserAuthRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin"})

    if not verify_password(data.password, current_user.password_hash):
        raise HTTPException(status_code=403, detail="Senha incorreta!")

    current = db.query(Product).filter(Product.id == product_id).first()
    if current is None:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    db.delete(current)
    db.commit()
    return {"message": "Produto excluido"}
