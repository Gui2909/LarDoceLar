from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String

from database.connection import Base


class CashFlow(Base):
    __tablename__ = "cash_flow"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    cash_session_id = Column(Integer, ForeignKey("cash_sessions.id"), nullable=True)
    type = Column(String, nullable=False, default="ENTRADA")
    amount = Column(Float, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    payment_method = Column(String, nullable=True)