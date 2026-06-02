from app.api.routes.agent import router as agent_router
from app.api.routes.auth import router as auth_router
from app.api.routes.confirmations import router as confirmations_router
from app.api.routes.memory import router as memory_router
from app.api.routes.model_profiles import router as model_profiles_router
from app.api.routes.novels import router as novels_router

__all__ = [
    "agent_router",
    "auth_router",
    "confirmations_router",
    "memory_router",
    "model_profiles_router",
    "novels_router",
]
