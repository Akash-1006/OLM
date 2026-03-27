# models/lead.py
from sqlalchemy import Column, Integer, String, Float, DateTime, BigInteger, Text
from datetime import datetime
from db import Base

class Lead(Base):
    __tablename__ = "leads"

    id            = Column(Integer, primary_key=True)
    company_name  = Column(String(255))
    client_name   = Column(String(255))           # contact person
    client_phone  = Column(String(20))
    site_status   = Column(String(50))            # work status: Visited/Quoted/Won/Lost...
    stage         = Column(String(50))            # Pile/Footing/Slab/Column/Flooring
    material      = Column(String(50))            # Ready Mix/Cement/Aggregate/Sand/Steel
    grade         = Column(String(20))            # M25 etc (optional)
    quantity      = Column(String(50))            # entered as string to support units
    remarks       = Column(Text)                  # optional notes
    photo_paths   = Column(Text)                  # comma-separated file paths on disk
    latitude      = Column(Float, nullable=True)
    longitude     = Column(Float, nullable=True)
    location      = Column(String(255))           # "lat,lng" string for display
    sales_exec_id   = Column(BigInteger)            # Telegram user ID
    sales_exec_name = Column(String(255))           # Telegram display name (saved at submit time)
    last_followup_at = Column(DateTime, nullable=True) # Last time a reminder was successfully sent
    created_at      = Column(DateTime, default=datetime.utcnow)