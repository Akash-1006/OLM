from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from modules.form_engine.models import CustomField, FieldGroup, FormVersion
from modules.tenants.models import Client
from typing import List, Dict, Any
import uuid

router = APIRouter()

@router.get("/form-config")
async def get_form_config(
    client_id: uuid.UUID,
    form_type: str = "lead_create",
    db: AsyncSession = Depends(get_db)
):
    # Fetch client branding
    client_stmt = select(Client).where(Client.id == client_id)
    client = (await db.execute(client_stmt)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Fetch field groups
    groups_stmt = select(FieldGroup).where(FieldGroup.client_id == client_id).order_by(FieldGroup.display_order)
    groups = (await db.execute(groups_stmt)).scalars().all()

    # Fetch fields
    fields_stmt = select(CustomField).where(CustomField.client_id == client_id).order_by(CustomField.display_order)
    fields = (await db.execute(fields_stmt)).scalars().all()

    # Organize fields into groups
    sections = []
    group_map = {str(g.id): g for g in groups}
    fields_by_group = {}

    for field in fields:
        gid = str(field.group_id) if field.group_id else "default"
        if gid not in fields_by_group:
            fields_by_group[gid] = []
        fields_by_group[gid].append({
            "key": field.key,
            "label": field.label,
            "type": field.field_type,
            "required": field.is_required,
            "placeholder": field.placeholder,
            "options": field.options,
            "validation": field.validation_rules,
            "conditional": field.conditional_rule,
            "metadata": field.metadata_config
        })

    for gid, group_fields in fields_by_group.items():
        if gid == "default":
            sections.append({
                "key": "default",
                "label": "General",
                "fields": group_fields
            })
        else:
            group = group_map.get(gid)
            if group:
                sections.append({
                    "key": group.key,
                    "label": group.name,
                    "icon": group.icon,
                    "fields": group_fields
                })

    return {
        "client": {
            "name": client.name,
            "branding": client.branding
        },
        "sections": sections
    }
