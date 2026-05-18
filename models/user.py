from sqlalchemy import Column, Integer, String

from database.connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    role = Column(String, nullable=False, default="cashier")
    password_hash = Column(String, nullable=False)

