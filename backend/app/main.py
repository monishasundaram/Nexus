from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import dashboard, health

app = FastAPI(title="NEXUS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])