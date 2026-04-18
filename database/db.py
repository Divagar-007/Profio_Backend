# database/db.py
# Handles SQLAlchemy engine creation and session lifecycle
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Create the SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,       # Verify connections before using them
    pool_size=10,             # Connection pool size
    max_overflow=20,          # Extra connections beyond pool_size
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Base class for all ORM models
Base = declarative_base()


def get_db():

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
