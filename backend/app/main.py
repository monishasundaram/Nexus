from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import comparisons, dashboard, environments, graph, health, scenarios, simulations

app = FastAPI(title="NEXUS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(environments.router, prefix="/api", tags=["environments"])
app.include_router(graph.router, prefix="/api", tags=["graph"])
app.include_router(scenarios.router, prefix="/api", tags=["scenarios"])
app.include_router(simulations.router, prefix="/api", tags=["simulations"])
app.include_router(comparisons.router, prefix="/api", tags=["comparisons"])

@app.get("/", include_in_schema=False)
def root():
    return {"name": "NEXUS API", "docs": "/docs", "health": "/api/health"}