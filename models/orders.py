from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

from database.connection import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, nullable=False)
    total = Column(Float, nullable=False, default=0)
    status = Column(String, nullable=False, default="ABERTO")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    payment_status = Column(String, default="PAGO")
    payment_method = Column(String, nullable=True)
    cash_session_id = Column(Integer, nullable=True)