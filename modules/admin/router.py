from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from core.database import get_db
from modules.tenants.models import Client
from modules.form_engine.models import FieldGroup, CustomField
from typing import List, Dict, Any
import uuid
import datetime

router = APIRouter()

# --- Client CRUD ---
@router.get("/clients")
async def list_clients(db: AsyncSession = Depends(get_db)):
    stmt = select(Client)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/clients/{client_id}")
async def get_client(client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(Client).where(Client.id == client_id)
    client = (await db.execute(stmt)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.post("/clients")
async def create_client(data: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    expires_at = None
    if data.get("expires_at"):
        expires_at = datetime.datetime.fromisoformat(data["expires_at"])

    client = Client(
        name=data["name"],
        slug=data["slug"],
        bot_token=data["bot_token"],
        branding=data.get("branding", {}),
        settings=data.get("settings", {}),
        status=data.get("status", "active"),
        plan=data.get("plan", "starter"),
        expires_at=expires_at
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client

@router.patch("/clients/{client_id}")
async def update_client(client_id: uuid.UUID, data: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    stmt = select(Client).where(Client.id == client_id)
    client = (await db.execute(stmt)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if "name" in data: client.name = data["name"]
    if "status" in data: client.status = data["status"]
    if "branding" in data: client.branding = data["branding"]
    if "settings" in data: client.settings = data["settings"]
    if "plan" in data: client.plan = data["plan"]
    if "expires_at" in data:
        client.expires_at = datetime.datetime.fromisoformat(data["expires_at"]) if data["expires_at"] else None

    await db.commit()
    await db.refresh(client)
    return client

@router.delete("/clients/{client_id}")
async def delete_client(client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = delete(Client).where(Client.id == client_id)
    await db.execute(stmt)
    await db.commit()
    return {"status": "ok"}

# --- Form Builder (Groups & Fields) ---
@router.get("/clients/{client_id}/groups")
async def list_groups(client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(FieldGroup).where(FieldGroup.client_id == client_id).order_by(FieldGroup.display_order)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/clients/{client_id}/groups")
async def create_group(client_id: uuid.UUID, data: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    group = FieldGroup(
        client_id=client_id,
        name=data["name"],
        key=data["key"],
        icon=data.get("icon"),
        display_order=data.get("display_order", 0)
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group

@router.get("/clients/{client_id}/fields")
async def list_fields(client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(CustomField).where(CustomField.client_id == client_id).order_by(CustomField.display_order)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/clients/{client_id}/fields")
async def create_field(client_id: uuid.UUID, data: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    field = CustomField(
        client_id=client_id,
        group_id=uuid.UUID(data["group_id"]) if data.get("group_id") else None,
        key=data["key"],
        label=data["label"],
        field_type=data["field_type"],
        is_required=data.get("is_required", False),
        is_searchable=data.get("is_searchable", False),
        options=data.get("options"),
        validation_rules=data.get("validation_rules", []),
        conditional_rule=data.get("conditional_rule"),
        display_order=data.get("display_order", 0)
    )
    db.add(field)
    await db.commit()
    await db.refresh(field)
    return field

@router.delete("/fields/{field_id}")
async def delete_field(field_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = delete(CustomField).where(CustomField.id == field_id)
    await db.execute(stmt)
    await db.commit()
    return {"status": "ok"}
