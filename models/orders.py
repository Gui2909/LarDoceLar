from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

from database.connection import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    total = Column(Float, nullable=False, default=0)
    status = Column(String, nullable=False, default="ABERTO")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)