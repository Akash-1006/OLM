from sqlalchemy import Column, String, JSON, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
import datetime
import uuid

class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    bot_token = Column(String(255), unique=True, nullable=False)
    status = Column(String(30), server_default="active")
    webhook_url = Column(String)
    branding = Column(JSON, server_default="{}")
    settings = Column(JSON, server_default="{}")
    plan = Column(String(50), server_default="starter")
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.datetime.now)
