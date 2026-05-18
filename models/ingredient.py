from sqlalchemy import Column, Integer, String
from database.connection import Base

class Ingredient(Base):
    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    category = Column(String)
    