from sqlalchemy import Boolean, Column, Float, Integer, String

from database.connection import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    category = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)