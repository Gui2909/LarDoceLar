from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

from database.connection import Base


class CashSession(Base):
    __tablename__ = "cash_sessions"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, nullable=False, default="ABERTO")
    opening_amount = Column(Float, nullable=False, default=0)
    closing_amount = Column(Float, nullable=True)
    opened_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at = Column(DateTime, nullable=True)
