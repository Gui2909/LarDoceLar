import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL não definida. Copie .env.example para .env ou exporte a variável."
    )

engine = create_engine(
    DATABASE_URL,
    client_encoding="utf8"
)

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()