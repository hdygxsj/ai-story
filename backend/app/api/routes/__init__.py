from app.api.routes.agent import router as agent_router
from app.api.routes.agent_tools import router as agent_tools_router
from app.api.routes.auth import router as auth_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.confirmations import router as confirmations_router
from app.api.routes.local_agent_skill import router as local_agent_skill_router
from app.api.routes.memory import router as memory_router
from app.api.routes.materials import router as materials_router
from app.api.routes.model_profiles import router as model_profiles_router
from app.api.routes.novels import router as novels_router
from app.api.routes.rag import router as rag_router
from app.api.routes.search import router as search_router

__all__ = [
    "agent_router",
    "agent_tools_router",
    "auth_router",
    "conversations_router",
    "confirmations_router",
    "local_agent_skill_router",
    "memory_router",
    "materials_router",
    "model_profiles_router",
    "novels_router",
    "rag_router",
    "search_router",
]
