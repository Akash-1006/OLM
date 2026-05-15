from sqlalchemy import Column, String, BigInteger, JSON, DateTime, ForeignKey, text, ARRAY, Text, TypeDecorator, Integer
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR, ARRAY as PG_ARRAY
from core.database import Base
import datetime

class TSVector(TypeDecorator):
    impl = Text
    cache_ok = True

class Lead(Base):
    __tablename__ = "leads"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    form_version_id = Column(UUID(as_uuid=True), ForeignKey("form_versions.id"))

    sales_exec_id = Column(BigInteger, nullable=False)
    sales_exec_name = Column(String(255))
    company_name = Column(String(255))
    client_phone = Column(String(30))
    site_status = Column(String(50), default="New")

    data = Column(JSON, nullable=False, server_default="{}")

    search_vector = Column(TSVector)
    searchable_tags = Column(JSON) # Use JSON for SQLite compatibility, cast to ARRAY in PG

    next_followup_date = Column(DateTime(timezone=True))
    last_followup_at = Column(DateTime(timezone=True))
    last_user_update_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.datetime.now)

class LeadUpdate(Base):
    __tablename__ = "lead_updates"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    lead_id = Column(BigInteger, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(UUID(as_uuid=True), nullable=False)
    sales_exec_id = Column(BigInteger)
    sales_exec_name = Column(String(255))
    data_before = Column(JSON)
    data_after = Column(JSON)
    changed_fields = Column(JSON)
    action = Column(String(50), default="update")
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
