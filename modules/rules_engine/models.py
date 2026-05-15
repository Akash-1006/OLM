from sqlalchemy import Column, String, Integer, Boolean, JSON, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
import uuid

class WorkflowRule(Base):
    __tablename__ = "workflow_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255))
    trigger_type = Column(String(50))
    trigger_config = Column(JSON)
    conditions = Column(JSON)
    actions = Column(JSON)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
