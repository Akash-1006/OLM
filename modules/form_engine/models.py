from sqlalchemy import Column, String, Integer, Boolean, JSON, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
import uuid

class FieldGroup(Base):
    __tablename__ = "field_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    key = Column(String(100), nullable=False)
    description = Column(String)
    icon = Column(String(100))
    display_order = Column(Integer, default=0)
    is_collapsible = Column(Boolean, default=False)
    is_repeatable = Column(Boolean, default=False)
    conditional_rule = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

class CustomField(Base):
    __tablename__ = "custom_fields"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(UUID(as_uuid=True), ForeignKey("field_groups.id", ondelete="SET NULL"))
    key = Column(String(100), nullable=False)
    label = Column(String(255), nullable=False)
    field_type = Column(String(50), nullable=False)
    placeholder = Column(String)
    helper_text = Column(String)
    default_value = Column(JSON)
    options = Column(JSON)
    validation_rules = Column(JSON, server_default="[]")
    conditional_rule = Column(JSON)
    display_order = Column(Integer, default=0)
    is_required = Column(Boolean, default=False)
    is_searchable = Column(Boolean, default=False)
    is_reportable = Column(Boolean, default=False)
    is_hidden = Column(Boolean, default=False)
    metadata_config = Column(JSON, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

class FormVersion(Base):
    __tablename__ = "form_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    label = Column(String(100))
    schema_snapshot = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=False)
    published_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
