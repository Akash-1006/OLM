# db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL

# SQLite engine — check_same_thread=False needed for Flask+APScheduler
engine = create_engine(
    DATABASE_URL,
    connect_args={'check_same_thread': False}  # SQLite only
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# All models inherit from Base
Base = declarative_base()

# Module-level session used by handlers and scheduler
db_session = SessionLocal()

def get_session():
    """Use this in request-scoped contexts for thread safety."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()