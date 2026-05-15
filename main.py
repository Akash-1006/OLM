from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os
from core.config import settings
from core.cache import cache
from modules.form_engine.router import router as form_router
from modules.leads.router import router as lead_router
from modules.admin.router import router as admin_router
from core.database import engine, Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await cache.connect()
    yield
    # Shutdown
    await cache.disconnect()

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(form_router, prefix=settings.API_V1_STR)
app.include_router(lead_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=f"{settings.API_V1_STR}/admin")

@app.get("/miniapp", response_class=HTMLResponse)
async def serve_miniapp():
    with open(os.path.join("miniapp", "index.html"), "r") as f:
        return f.read()

@app.get("/admin", response_class=HTMLResponse)
async def serve_admin():
    with open(os.path.join("admin", "index.html"), "r") as f:
        return f.read()

@app.get("/")
async def root():
    return {"message": "Dynamic Form Engine API"}
