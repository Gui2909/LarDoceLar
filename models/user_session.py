from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from database.connection import Base


class UserSession(Base):
    __tablename__ = "user_sessions"

    token = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
