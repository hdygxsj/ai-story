from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    agent_router,
    auth_router,
    confirmations_router,
    memory_router,
    materials_router,
    model_profiles_router,
    novels_router,
    rag_router,
)
from app.core.config import settings


app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(model_profiles_router)
app.include_router(novels_router)
app.include_router(memory_router)
app.include_router(materials_router)
app.include_router(agent_router)
app.include_router(confirmations_router)
app.include_router(rag_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}
