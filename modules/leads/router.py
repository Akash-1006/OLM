from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from modules.leads.models import Lead, LeadUpdate
from modules.form_engine.models import CustomField
from modules.validators.engine import DynamicValidator
from typing import List, Dict, Any, Optional
import uuid
import json
import os

router = APIRouter()
validator = DynamicValidator()

@router.post("/leads")
async def submit_lead(
    request: Request,
    client_id: uuid.UUID = Form(...),
    sales_exec_id: int = Form(...),
    sales_exec_name: str = Form(None),
    data: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        parsed_data = json.loads(data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid data JSON")

    # Fetch fields metadata for validation and search extraction
    fields_stmt = select(CustomField).where(CustomField.client_id == client_id)
    fields_meta_rows = (await db.execute(fields_stmt)).scalars().all()
    fields_meta = [
        {
            "key": f.key,
            "validation_rules": f.validation_rules,
            "is_searchable": f.is_searchable
        } for f in fields_meta_rows
    ]

    # Validate
    errors = validator.validate_submission(fields_meta, parsed_data)
    if errors:
        return {"status": "error", "errors": errors}

    # Extract core fields
    company_name = parsed_data.get("company_name")
    client_phone = parsed_data.get("client_phone")
    site_status = parsed_data.get("site_status", "New")

    # Extract searchable tags
    searchable_tags = []
    for f in fields_meta:
        if f["is_searchable"] and f["key"] in parsed_data:
            val = parsed_data[f["key"]]
            if isinstance(val, list):
                searchable_tags.extend([str(v) for v in val])
            else:
                searchable_tags.append(str(val))

    # Simple search vector (concat all values for now)
    search_text = " ".join([str(v) for v in parsed_data.values() if v])

    lead = Lead(
        client_id=client_id,
        sales_exec_id=sales_exec_id,
        sales_exec_name=sales_exec_name,
        company_name=company_name,
        client_phone=client_phone,
        site_status=site_status,
        data=parsed_data,
        searchable_tags=searchable_tags,
        search_vector=search_text
    )

    db.add(lead)
    await db.commit()
    await db.refresh(lead)

    return {"status": "ok", "lead_id": lead.id}

@router.get("/leads/{lead_id}")
async def get_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Lead).where(Lead.id == lead_id)
    lead = (await db.execute(stmt)).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead
