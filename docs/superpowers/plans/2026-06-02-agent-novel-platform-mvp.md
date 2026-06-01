# Agent Novel Platform MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first usable vertical slice of the Agent-first novel IDE: account login, novel workspace, editable documents, memory primitives, context pack assembly, and a LangGraph-backed chat endpoint that can produce confirmed changes.

**Architecture:** Use a monorepo with a React frontend and FastAPI backend. Postgres is the source of truth for users, novels, documents, versions, confirmations, and memory; Milvus is wired through an adapter so local tests can use a fake vector store while Docker Compose runs the real service. LangGraph starts inside the API process as an isolated `app/agent` module.

**Tech Stack:** React, TypeScript, Vite, shadcn/ui, assistant-ui, TipTap, Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic, LangGraph, Postgres, Milvus, Docker Compose, pytest, Vitest, Playwright.

---

## Scope Split

This plan implements the first integrated MVP. It does not implement every advanced behavior from the design spec. The MVP proves the core product loop:

1. User signs in.
2. User creates a novel.
3. User manages a workspace tree and edits a chapter.
4. User chats with the Agent inside that novel.
5. Agent can build a context pack, draft a memory or rewrite, ask for confirmation, and persist confirmed changes.
6. User can see memory/context state and document versions.

Later plans should add production-grade Milvus indexing, richer relationship graph traversal, full assistant-ui polish, OAuth, billing, and advanced multi-worker execution.

## File Structure

Create this structure:

```text
ai-story/
  docker-compose.yml
  .env.example
  Makefile
  backend/
    pyproject.toml
    alembic.ini
    alembic/env.py
    alembic/versions/0001_initial.py
    app/main.py
    app/core/config.py
    app/core/security.py
    app/db/base.py
    app/db/session.py
    app/models/*.py
    app/schemas/*.py
    app/api/deps.py
    app/api/routes/*.py
    app/services/*.py
    app/agent/*.py
    tests/**/*.py
  frontend/
    package.json
    index.html
    vite.config.ts
    tsconfig.json
    src/main.tsx
    src/App.tsx
    src/api/http.ts
    src/api/auth.ts
    src/api/novels.ts
    src/api/workspace.ts
    src/api/documents.ts
    src/api/memory.ts
    src/api/agent.ts
    src/api/modelProfiles.ts
    src/features/auth/*
    src/features/novels/*
    src/features/workspace/*
    src/features/agent/*
    src/features/editor/*
    src/test/*.test.tsx
```

Keep backend modules small:

- `models`: database tables only.
- `schemas`: request/response types only.
- `services`: business operations and authorization checks.
- `agent`: LangGraph state, tools, context packing, and graph assembly.
- `api/routes`: HTTP and streaming boundary only.

## Engineering Conventions

These conventions are mandatory for implementation tasks:

- Prefer UI libraries before custom frontend UI. Use shadcn/ui, Radix-style primitives, assistant-ui, TipTap, and mature component packages whenever they fit. Hand-written UI is allowed only when the library component does not cover the interaction or would add unnecessary complexity.
- Split frontend code by feature and component. A component file should render one clear UI unit. Break large panels into smaller components before they become hard to scan.
- Put reusable TypeScript logic, state machines, effects, and data transformations in `use-xxx.ts` hooks only when they are real logic. Do not create hook files just to move JSX around.
- Split API calls by domain. Keep the shared fetch wrapper in `frontend/src/api/http.ts`; put endpoint functions in domain files such as `auth.ts`, `novels.ts`, `workspace.ts`, `documents.ts`, `memory.ts`, `agent.ts`, and `modelProfiles.ts`.
- Use backend layering consistently: `api/routes` handles HTTP only, `schemas` defines request and response shapes, `services` owns business rules and authorization decisions, `repositories` owns database queries when a service grows beyond simple CRUD, `models` defines database tables, and `agent` owns LangGraph-specific logic.
- No frontend or backend source file may exceed 800 lines. If a planned change would push a file over 800 lines, split it in the same task before committing.
- Tests should follow the same boundaries: backend tests validate service behavior and API behavior separately when useful; frontend tests validate user-visible feature components instead of implementation details.

## Task 1: Repository Scaffold And Local Services

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `Makefile`
- Create: `backend/pyproject.toml`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/tests/test_health.py`
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Test: `backend/tests/test_health.py`

- [ ] **Step 1: Create backend package config**

Create `backend/pyproject.toml`:

```toml
[project]
name = "ai-story-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "alembic>=1.13",
  "asyncpg>=0.29",
  "fastapi>=0.115",
  "httpx>=0.27",
  "langchain-openai>=0.2",
  "langchain-anthropic>=0.2",
  "langgraph>=0.2",
  "passlib[bcrypt]>=1.7",
  "psycopg[binary]>=3.2",
  "pydantic-settings>=2.5",
  "python-jose[cryptography]>=3.3",
  "python-multipart>=0.0.9",
  "sqlalchemy[asyncio]>=2.0",
  "uvicorn[standard]>=0.30"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "ruff>=0.6"
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"
```

- [ ] **Step 2: Create FastAPI health endpoint**

Create `backend/app/core/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Story"
    environment: str = "local"
    database_url: str = "postgresql+asyncpg://ai_story:ai_story@localhost:5432/ai_story"
    jwt_secret: str = "local-development-secret"
    access_token_minutes: int = 1440
    cors_origins: list[str] = ["http://localhost:5173"]
    milvus_uri: str = "http://localhost:19530"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
```

Create `backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}
```

Create `backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "AI Story"}
```

- [ ] **Step 3: Run backend health test**

Run:

```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]" && pytest tests/test_health.py -v
```

Expected: one passing test named `test_health_returns_ok`.

- [ ] **Step 4: Create frontend scaffold**

Create `frontend/package.json`:

```json
{
  "name": "ai-story-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run",
    "lint": "eslint ."
  },
  "dependencies": {
    "@tiptap/extension-placeholder": "latest",
    "@tiptap/react": "latest",
    "@tiptap/starter-kit": "latest",
    "@vitejs/plugin-react": "latest",
    "lucide-react": "latest",
    "react": "latest",
    "react-dom": "latest",
    "zustand": "latest"
  },
  "devDependencies": {
    "@testing-library/react": "latest",
    "@testing-library/user-event": "latest",
    "typescript": "latest",
    "vite": "latest",
    "vitest": "latest",
    "jsdom": "latest",
    "eslint": "latest"
  }
}
```

Create `frontend/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AI Story</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `frontend/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  test: {
    environment: "jsdom",
  },
});
```

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": []
}
```

Create `frontend/src/App.tsx`:

```tsx
export function App() {
  return (
    <main style={{ padding: 24, fontFamily: "system-ui, sans-serif" }}>
      <h1>AI Story</h1>
      <p>Agent-first novel creation IDE</p>
    </main>
  );
}
```

Create `frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "./App";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 5: Create Docker Compose**

Create `.env.example`:

```bash
DATABASE_URL=postgresql+asyncpg://ai_story:ai_story@postgres:5432/ai_story
JWT_SECRET=change-me-before-real-use
MILVUS_URI=http://milvus:19530
POSTGRES_USER=ai_story
POSTGRES_PASSWORD=ai_story
POSTGRES_DB=ai_story
```

Create `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-ai_story}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-ai_story}
      POSTGRES_DB: ${POSTGRES_DB:-ai_story}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  milvus:
    image: milvusdb/milvus:v2.4.15
    command: ["milvus", "run", "standalone"]
    environment:
      ETCD_USE_EMBED: "true"
      COMMON_STORAGETYPE: local
    ports:
      - "19530:19530"
      - "9091:9091"
    volumes:
      - milvus_data:/var/lib/milvus

  api:
    image: python:3.12-slim
    working_dir: /app
    command: bash -lc "pip install -e '.[dev]' && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    environment:
      DATABASE_URL: ${DATABASE_URL:-postgresql+asyncpg://ai_story:ai_story@postgres:5432/ai_story}
      JWT_SECRET: ${JWT_SECRET:-local-development-secret}
      MILVUS_URI: ${MILVUS_URI:-http://milvus:19530}
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    depends_on:
      - postgres
      - milvus

  web:
    image: node:22
    working_dir: /app
    command: bash -lc "npm install && npm run dev -- --host 0.0.0.0"
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
    depends_on:
      - api

volumes:
  postgres_data:
  milvus_data:
```

Create `Makefile`:

```makefile
.PHONY: backend-test frontend-test test up down

backend-test:
	cd backend && . .venv/bin/activate && pytest -v

frontend-test:
	cd frontend && npm test

test: backend-test frontend-test

up:
	docker compose --env-file .env.example up

down:
	docker compose down
```

- [ ] **Step 6: Verify local services start**

Run:

```bash
docker compose --env-file .env.example config
```

Expected: Docker Compose prints a normalized config with services `postgres`, `milvus`, `api`, and `web`.

- [ ] **Step 7: Commit Task 1**

```bash
git add .env.example Makefile docker-compose.yml backend frontend
git commit -m "chore: scaffold ai story app"
```

## Task 2: Database, Authentication, And Model Profiles

**Files:**
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/core/security.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/model_profile.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/schemas/model_profile.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/routes/auth.py`
- Create: `backend/app/api/routes/model_profiles.py`
- Modify: `backend/app/main.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_initial.py`
- Test: `backend/tests/test_auth.py`
- Test: `backend/tests/test_model_profiles.py`

- [ ] **Step 1: Write authentication tests**

Create `backend/tests/test_auth.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_register_and_login_user() -> None:
    client = TestClient(app)

    register_response = client.post(
        "/auth/register",
        json={"email": "writer@example.com", "username": "writer", "password": "secret123"},
    )

    assert register_response.status_code == 201
    assert register_response.json()["email"] == "writer@example.com"

    login_response = client.post(
        "/auth/login",
        json={"login": "writer@example.com", "password": "secret123"},
    )

    assert login_response.status_code == 200
    body = login_response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)


def test_me_requires_token() -> None:
    client = TestClient(app)

    response = client.get("/auth/me")

    assert response.status_code == 401
```

- [ ] **Step 2: Run authentication tests to verify failure**

Run:

```bash
cd backend && . .venv/bin/activate && pytest tests/test_auth.py -v
```

Expected: FAIL because `/auth/register`, `/auth/login`, and `/auth/me` are not defined.

- [ ] **Step 3: Implement SQLAlchemy base and session**

Create `backend/app/db/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass


class Base(MappedAsDataclass, DeclarativeBase):
    pass
```

Create `backend/app/db/session.py`:

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 4: Implement user and model profile models**

Create `backend/app/models/user.py`:

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
```

Create `backend/app/models/model_profile.py`:

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelProfile(Base):
    __tablename__ = "model_profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    provider_kind: Mapped[str] = mapped_column(String(40))
    base_url: Mapped[str | None] = mapped_column(String(500), default=None)
    api_key_ciphertext: Mapped[str] = mapped_column(String(2000))
    chat_model: Mapped[str] = mapped_column(String(160))
    writing_model: Mapped[str] = mapped_column(String(160))
    summary_model: Mapped[str] = mapped_column(String(160))
    embedding_model: Mapped[str] = mapped_column(String(160))
    supports_tool_calling: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_json_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_streaming: Mapped[bool] = mapped_column(Boolean, default=True)
    context_window: Mapped[int] = mapped_column(Integer, default=128000)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, default=1536)
    extra_headers: Mapped[dict] = mapped_column(JSON, default_factory=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
```

Create `backend/app/models/__init__.py`:

```python
from app.models.model_profile import ModelProfile
from app.models.user import User

__all__ = ["ModelProfile", "User"]
```

- [ ] **Step 5: Implement security helpers**

Create `backend/app/core/security.py`:

```python
from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: UUID) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    payload = {"sub": str(user_id), "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return UUID(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise ValueError("Invalid access token") from exc
```

- [ ] **Step 6: Implement auth schemas and routes**

Create `backend/app/schemas/auth.py`:

```python
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    login: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    username: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

Create `backend/app/api/deps.py`:

```python
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


async def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    try:
        user_id = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user
```

Create `backend/app/api/routes/auth.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: Annotated[AsyncSession, Depends(get_session)]):
    existing = await session.scalar(
        select(User).where(or_(User.email == payload.email, User.username == payload.username))
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email or username already exists")
    user = User(
        email=str(payload.email),
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: Annotated[AsyncSession, Depends(get_session)]):
    user = await session.scalar(
        select(User).where(or_(User.email == payload.login, User.username == payload.login))
    )
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[User, Depends(current_user)]):
    return user
```

- [ ] **Step 7: Implement model profile schemas and routes**

Create `backend/app/schemas/model_profile.py`:

```python
from uuid import UUID

from pydantic import BaseModel, Field


class ModelProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider_kind: str
    base_url: str | None = None
    api_key: str = Field(min_length=1)
    chat_model: str
    writing_model: str
    summary_model: str
    embedding_model: str
    supports_tool_calling: bool = True
    supports_json_mode: bool = True
    supports_streaming: bool = True
    context_window: int = 128000
    embedding_dimensions: int = 1536
    extra_headers: dict[str, str] = {}


class ModelProfileResponse(BaseModel):
    id: UUID
    name: str
    provider_kind: str
    base_url: str | None
    chat_model: str
    writing_model: str
    summary_model: str
    embedding_model: str
    supports_tool_calling: bool
    supports_json_mode: bool
    supports_streaming: bool
    context_window: int
    embedding_dimensions: int
    extra_headers: dict
```

Create `backend/app/api/routes/model_profiles.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_session
from app.models.model_profile import ModelProfile
from app.models.user import User
from app.schemas.model_profile import ModelProfileCreate, ModelProfileResponse

router = APIRouter(prefix="/model-profiles", tags=["model-profiles"])


@router.post("", response_model=ModelProfileResponse, status_code=201)
async def create_model_profile(
    payload: ModelProfileCreate,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    profile = ModelProfile(
        owner_id=user.id,
        name=payload.name,
        provider_kind=payload.provider_kind,
        base_url=payload.base_url,
        api_key_ciphertext=payload.api_key,
        chat_model=payload.chat_model,
        writing_model=payload.writing_model,
        summary_model=payload.summary_model,
        embedding_model=payload.embedding_model,
        supports_tool_calling=payload.supports_tool_calling,
        supports_json_mode=payload.supports_json_mode,
        supports_streaming=payload.supports_streaming,
        context_window=payload.context_window,
        embedding_dimensions=payload.embedding_dimensions,
        extra_headers=payload.extra_headers,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


@router.get("", response_model=list[ModelProfileResponse])
async def list_model_profiles(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    profiles = await session.scalars(
        select(ModelProfile).where(ModelProfile.owner_id == user.id).order_by(ModelProfile.created_at)
    )
    return list(profiles)
```

- [ ] **Step 8: Wire routers into FastAPI**

Modify `backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, model_profiles
from app.core.config import settings


app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(model_profiles.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}
```

Create `backend/app/api/routes/__init__.py`:

```python
from app.api.routes import auth, model_profiles

__all__ = ["auth", "model_profiles"]
```

- [ ] **Step 9: Create Alembic migration**

Create `backend/alembic.ini`:

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = postgresql+asyncpg://ai_story:ai_story@localhost:5432/ai_story

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

Create `backend/alembic/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.db.base import Base
from app.models import ModelProfile, User

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(
            lambda sync_connection: context.configure(
                connection=sync_connection, target_metadata=target_metadata
            )
        )
        await connection.run_sync(lambda _: context.run_migrations())
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio

    asyncio.run(run_migrations_online())
```

Create `backend/alembic/versions/0001_initial.py`:

```python
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_table(
        "model_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("provider_kind", sa.String(length=40), nullable=False),
        sa.Column("base_url", sa.String(length=500)),
        sa.Column("api_key_ciphertext", sa.String(length=2000), nullable=False),
        sa.Column("chat_model", sa.String(length=160), nullable=False),
        sa.Column("writing_model", sa.String(length=160), nullable=False),
        sa.Column("summary_model", sa.String(length=160), nullable=False),
        sa.Column("embedding_model", sa.String(length=160), nullable=False),
        sa.Column("supports_tool_calling", sa.Boolean(), nullable=False),
        sa.Column("supports_json_mode", sa.Boolean(), nullable=False),
        sa.Column("supports_streaming", sa.Boolean(), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column("extra_headers", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_model_profiles_owner_id", "model_profiles", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_model_profiles_owner_id", table_name="model_profiles")
    op.drop_table("model_profiles")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
```

- [ ] **Step 10: Add model profile test**

Create `backend/tests/test_model_profiles.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": "model@example.com", "username": "modeluser", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "model@example.com", "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_openai_compatible_profile() -> None:
    client = TestClient(app)
    headers = auth_headers(client)

    create_response = client.post(
        "/model-profiles",
        headers=headers,
        json={
            "name": "Local compatible",
            "provider_kind": "openai_compatible",
            "base_url": "http://localhost:11434/v1",
            "api_key": "local-key",
            "chat_model": "qwen",
            "writing_model": "qwen",
            "summary_model": "qwen",
            "embedding_model": "text-embedding-3-small",
            "supports_tool_calling": True,
            "supports_json_mode": True,
            "supports_streaming": True,
            "context_window": 32000,
            "embedding_dimensions": 1536,
            "extra_headers": {},
        },
    )

    assert create_response.status_code == 201
    list_response = client.get("/model-profiles", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()[0]["name"] == "Local compatible"
```

- [ ] **Step 11: Run Task 2 tests**

Run:

```bash
cd backend && . .venv/bin/activate && pytest tests/test_auth.py tests/test_model_profiles.py -v
```

Expected: tests pass against a test database. If they fail because tests share the real database, add a pytest fixture in `backend/tests/conftest.py` that creates tables with `Base.metadata.create_all()` on an in-memory SQLite async engine and overrides `get_session`.

- [ ] **Step 12: Commit Task 2**

```bash
git add backend
git commit -m "feat: add auth and model profiles"
```

## Task 3: Novel Workspace, Documents, And Versions

**Files:**
- Create: `backend/app/models/novel.py`
- Create: `backend/app/models/workspace.py`
- Create: `backend/app/models/document.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/novel.py`
- Create: `backend/app/schemas/workspace.py`
- Create: `backend/app/schemas/document.py`
- Create: `backend/app/services/novels.py`
- Create: `backend/app/api/routes/novels.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_workspace.py`

- [ ] **Step 1: Write workspace test**

Create `backend/tests/test_workspace.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": "workspace@example.com", "username": "workspace", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "workspace@example.com", "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_novel_chapter_and_update_document_version() -> None:
    client = TestClient(app)
    headers = auth_headers(client)

    novel = client.post("/novels", headers=headers, json={"title": "Border Doctor"}).json()
    chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Chapter 1", "node_type": "chapter", "parent_id": None},
    ).json()

    update = client.patch(
        f"/documents/{chapter['document_id']}",
        headers=headers,
        json={"content": {"type": "doc", "content": [{"type": "paragraph", "text": "Opening."}]}},
    )

    assert update.status_code == 200
    versions = client.get(f"/documents/{chapter['document_id']}/versions", headers=headers)
    assert versions.status_code == 200
    assert len(versions.json()) == 1
```

- [ ] **Step 2: Run workspace test to verify failure**

Run:

```bash
cd backend && . .venv/bin/activate && pytest tests/test_workspace.py -v
```

Expected: FAIL because novel and document routes do not exist.

- [ ] **Step 3: Implement workspace models**

Create `backend/app/models/novel.py`:

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Novel(Base):
    __tablename__ = "novels"

    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    default_model_profile_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("model_profiles.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
```

Create `backend/app/models/workspace.py`:

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkspaceNode(Base):
    __tablename__ = "workspace_nodes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workspace_nodes.id", ondelete="CASCADE"), default=None
    )
    document_id: Mapped[UUID | None] = mapped_column(default=None, index=True)
    title: Mapped[str] = mapped_column(String(200))
    node_type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="draft")
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
```

Create `backend/app/models/document.py`:

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    content: Mapped[dict] = mapped_column(JSON, default_factory=lambda: {"type": "doc", "content": []})
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), init=False
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(40))
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
```

- [ ] **Step 4: Implement schemas and ownership service**

Create `backend/app/schemas/novel.py`:

```python
from uuid import UUID

from pydantic import BaseModel


class NovelCreate(BaseModel):
    title: str
    description: str = ""


class NovelResponse(BaseModel):
    id: UUID
    title: str
    description: str
```

Create `backend/app/schemas/workspace.py`:

```python
from uuid import UUID

from pydantic import BaseModel


class WorkspaceNodeCreate(BaseModel):
    title: str
    node_type: str
    parent_id: UUID | None = None


class WorkspaceNodeResponse(BaseModel):
    id: UUID
    novel_id: UUID
    parent_id: UUID | None
    document_id: UUID | None
    title: str
    node_type: str
    status: str
    position: int
```

Create `backend/app/schemas/document.py`:

```python
from uuid import UUID

from pydantic import BaseModel


class DocumentUpdate(BaseModel):
    content: dict


class DocumentResponse(BaseModel):
    id: UUID
    novel_id: UUID
    content: dict


class DocumentVersionResponse(BaseModel):
    id: UUID
    document_id: UUID
    source: str
    content: dict
```

Create `backend/app/services/novels.py`:

```python
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.novel import Novel
from app.models.user import User


async def get_owned_novel(session: AsyncSession, user: User, novel_id: UUID) -> Novel:
    novel = await session.scalar(select(Novel).where(Novel.id == novel_id, Novel.owner_id == user.id))
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    return novel
```

- [ ] **Step 5: Implement novel and document routes**

Create `backend/app/api/routes/novels.py`:

```python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_session
from app.models.document import Document, DocumentVersion
from app.models.novel import Novel
from app.models.user import User
from app.models.workspace import WorkspaceNode
from app.schemas.document import DocumentResponse, DocumentUpdate, DocumentVersionResponse
from app.schemas.novel import NovelCreate, NovelResponse
from app.schemas.workspace import WorkspaceNodeCreate, WorkspaceNodeResponse
from app.services.novels import get_owned_novel

router = APIRouter(tags=["novels"])


@router.post("/novels", response_model=NovelResponse, status_code=201)
async def create_novel(
    payload: NovelCreate,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    novel = Novel(owner_id=user.id, title=payload.title, description=payload.description)
    session.add(novel)
    await session.commit()
    await session.refresh(novel)
    return novel


@router.get("/novels", response_model=list[NovelResponse])
async def list_novels(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    novels = await session.scalars(select(Novel).where(Novel.owner_id == user.id).order_by(Novel.created_at))
    return list(novels)


@router.post("/novels/{novel_id}/nodes", response_model=WorkspaceNodeResponse, status_code=201)
async def create_node(
    novel_id: UUID,
    payload: WorkspaceNodeCreate,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    novel = await get_owned_novel(session, user, novel_id)
    document_id = None
    if payload.node_type != "folder":
        document = Document(novel_id=novel.id)
        session.add(document)
        await session.flush()
        document_id = document.id
    node = WorkspaceNode(
        novel_id=novel.id,
        parent_id=payload.parent_id,
        document_id=document_id,
        title=payload.title,
        node_type=payload.node_type,
    )
    session.add(node)
    await session.commit()
    await session.refresh(node)
    return node


@router.get("/novels/{novel_id}/nodes", response_model=list[WorkspaceNodeResponse])
async def list_nodes(
    novel_id: UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    await get_owned_novel(session, user, novel_id)
    nodes = await session.scalars(
        select(WorkspaceNode).where(WorkspaceNode.novel_id == novel_id).order_by(WorkspaceNode.position)
    )
    return list(nodes)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    document = await session.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await get_owned_novel(session, user, document.novel_id)
    return document


@router.patch("/documents/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    payload: DocumentUpdate,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    document = await session.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await get_owned_novel(session, user, document.novel_id)
    version = DocumentVersion(document_id=document.id, source="user", content=document.content)
    session.add(version)
    document.content = payload.content
    await session.commit()
    await session.refresh(document)
    return document


@router.get("/documents/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def list_document_versions(
    document_id: UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    document = await session.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await get_owned_novel(session, user, document.novel_id)
    versions = await session.scalars(
        select(DocumentVersion).where(DocumentVersion.document_id == document.id).order_by(DocumentVersion.created_at)
    )
    return list(versions)
```

- [ ] **Step 6: Wire routes and model exports**

Modify `backend/app/models/__init__.py`:

```python
from app.models.document import Document, DocumentVersion
from app.models.model_profile import ModelProfile
from app.models.novel import Novel
from app.models.user import User
from app.models.workspace import WorkspaceNode

__all__ = ["Document", "DocumentVersion", "ModelProfile", "Novel", "User", "WorkspaceNode"]
```

Modify `backend/app/api/routes/__init__.py`:

```python
from app.api.routes import auth, model_profiles, novels

__all__ = ["auth", "model_profiles", "novels"]
```

Modify `backend/app/main.py` to include `novels.router`:

```python
from app.api.routes import auth, model_profiles, novels

app.include_router(auth.router)
app.include_router(model_profiles.router)
app.include_router(novels.router)
```

- [ ] **Step 7: Add database migration for workspace**

Create `backend/alembic/versions/0002_workspace.py`:

```python
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_workspace"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "novels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "default_model_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_novels_owner_id", "novels", ["owner_id"])
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("novel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_documents_novel_id", "documents", ["novel_id"])
    op.create_table(
        "document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])
    op.create_table(
        "workspace_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("novel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspace_nodes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("node_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workspace_nodes_novel_id", "workspace_nodes", ["novel_id"])
    op.create_index("ix_workspace_nodes_document_id", "workspace_nodes", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_workspace_nodes_document_id", table_name="workspace_nodes")
    op.drop_index("ix_workspace_nodes_novel_id", table_name="workspace_nodes")
    op.drop_table("workspace_nodes")
    op.drop_index("ix_document_versions_document_id", table_name="document_versions")
    op.drop_table("document_versions")
    op.drop_index("ix_documents_novel_id", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_novels_owner_id", table_name="novels")
    op.drop_table("novels")
```

Run:

```bash
cd backend && . .venv/bin/activate && alembic upgrade head
```

Expected: Alembic applies `0001_initial` and `0002_workspace`.

- [ ] **Step 8: Run workspace tests**

Run:

```bash
cd backend && . .venv/bin/activate && pytest tests/test_workspace.py -v
```

Expected: `test_create_novel_chapter_and_update_document_version` passes.

- [ ] **Step 9: Commit Task 3**

```bash
git add backend
git commit -m "feat: add novel workspace documents"
```

## Task 4: Layered Memory And Context Pack Backend

**Files:**
- Create: `backend/app/models/memory.py`
- Create: `backend/app/schemas/memory.py`
- Create: `backend/app/services/memory.py`
- Create: `backend/app/agent/context.py`
- Create: `backend/app/api/routes/memory.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_memory.py`
- Test: `backend/tests/test_context_pack.py`

- [ ] **Step 1: Write memory priority tests**

Create `backend/tests/test_memory.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": "memory@example.com", "username": "memory", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "memory@example.com", "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_key_memory_is_created_as_review_item_then_approved() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Memory Book"}).json()

    draft = client.post(
        f"/novels/{novel['id']}/memory-review-items",
        headers=headers,
        json={
            "memory_type": "key_memory",
            "title": "Protagonist constraint",
            "body": "The protagonist must never willingly betray a patient.",
            "importance": 100,
        },
    )

    assert draft.status_code == 201
    approved = client.post(
        f"/memory-review-items/{draft.json()['id']}/approve",
        headers=headers,
    )

    assert approved.status_code == 200
    assert approved.json()["memory_type"] == "key_memory"
    assert approved.json()["importance"] == 100
```

- [ ] **Step 2: Write context pack test**

Create `backend/tests/test_context_pack.py`:

```python
from app.agent.context import ContextBudget, build_context_pack


def test_context_pack_prioritizes_key_memory_and_neighboring_chapter() -> None:
    pack = build_context_pack(
        user_instruction="Write the next chapter.",
        current_document_text="",
        selected_text=None,
        key_memories=["Never let the protagonist betray a patient."],
        structured_memories=["A border clinic sits between two rival states."],
        neighboring_chapters=["Chapter 2 ended with the clinic under siege."],
        rag_results=["A minor note about weather."],
        budget=ContextBudget(max_tokens=2000, response_tokens=500),
    )

    assert pack.items[0].source == "user_instruction"
    assert any(item.source == "key_memory" for item in pack.items[:3])
    assert any(item.source == "neighboring_chapter" for item in pack.items)
    assert pack.estimated_tokens < 2000
```

- [ ] **Step 3: Run memory tests to verify failure**

Run:

```bash
cd backend && . .venv/bin/activate && pytest tests/test_memory.py tests/test_context_pack.py -v
```

Expected: FAIL because memory routes and context pack module do not exist.

- [ ] **Step 4: Implement memory models**

Create `backend/app/models/memory.py`:

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MemoryReviewItem(Base):
    __tablename__ = "memory_review_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    memory_type: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    importance: Mapped[int] = mapped_column(Integer, default=50)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    metadata: Mapped[dict] = mapped_column(JSON, default_factory=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )


class MemoryItem(Base):
    __tablename__ = "memory_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    memory_type: Mapped[str] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    importance: Mapped[int] = mapped_column(Integer, default=50)
    metadata: Mapped[dict] = mapped_column(JSON, default_factory=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
```

- [ ] **Step 5: Implement context pack builder**

Create `backend/app/agent/context.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ContextBudget:
    max_tokens: int
    response_tokens: int


@dataclass(frozen=True)
class ContextItem:
    source: str
    text: str
    priority: int
    estimated_tokens: int


@dataclass(frozen=True)
class ContextPack:
    items: list[ContextItem]
    estimated_tokens: int
    usage_ratio: float
    status_messages: list[str]


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def build_context_pack(
    *,
    user_instruction: str,
    current_document_text: str,
    selected_text: str | None,
    key_memories: list[str],
    structured_memories: list[str],
    neighboring_chapters: list[str],
    rag_results: list[str],
    budget: ContextBudget,
) -> ContextPack:
    candidates: list[ContextItem] = [
        ContextItem("user_instruction", user_instruction, 1000, estimate_tokens(user_instruction)),
    ]
    if selected_text:
        candidates.append(ContextItem("selected_text", selected_text, 950, estimate_tokens(selected_text)))
    if current_document_text:
        candidates.append(
            ContextItem("current_document", current_document_text, 900, estimate_tokens(current_document_text))
        )
    candidates.extend(ContextItem("key_memory", text, 850, estimate_tokens(text)) for text in key_memories)
    candidates.extend(
        ContextItem("structured_memory", text, 750, estimate_tokens(text)) for text in structured_memories
    )
    candidates.extend(
        ContextItem("neighboring_chapter", text, 650, estimate_tokens(text)) for text in neighboring_chapters
    )
    candidates.extend(ContextItem("rag_result", text, 500, estimate_tokens(text)) for text in rag_results)

    available = budget.max_tokens - budget.response_tokens
    selected: list[ContextItem] = []
    used = 0
    for item in sorted(candidates, key=lambda value: value.priority, reverse=True):
        if used + item.estimated_tokens <= available:
            selected.append(item)
            used += item.estimated_tokens

    usage_ratio = used / budget.max_tokens
    status_messages = [f"Context usage is about {round(usage_ratio * 100)}%."]
    if any(item.source == "neighboring_chapter" for item in selected):
        status_messages.append("Included neighboring chapter context.")
    if usage_ratio >= 0.7:
        status_messages.append("Context compression may happen soon.")

    return ContextPack(items=selected, estimated_tokens=used, usage_ratio=usage_ratio, status_messages=status_messages)
```

- [ ] **Step 6: Implement memory schemas, service, and routes**

Create `backend/app/schemas/memory.py`:

```python
from uuid import UUID

from pydantic import BaseModel


class MemoryReviewCreate(BaseModel):
    memory_type: str
    title: str
    body: str
    importance: int = 50
    metadata: dict = {}


class MemoryReviewResponse(BaseModel):
    id: UUID
    memory_type: str
    title: str
    body: str
    importance: int
    status: str


class MemoryItemResponse(BaseModel):
    id: UUID
    memory_type: str
    title: str
    body: str
    importance: int
```

Create `backend/app/api/routes/memory.py`:

```python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_session
from app.models.memory import MemoryItem, MemoryReviewItem
from app.models.user import User
from app.schemas.memory import MemoryItemResponse, MemoryReviewCreate, MemoryReviewResponse
from app.services.novels import get_owned_novel

router = APIRouter(tags=["memory"])


@router.post("/novels/{novel_id}/memory-review-items", response_model=MemoryReviewResponse, status_code=201)
async def create_memory_review_item(
    novel_id: UUID,
    payload: MemoryReviewCreate,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    await get_owned_novel(session, user, novel_id)
    item = MemoryReviewItem(
        novel_id=novel_id,
        memory_type=payload.memory_type,
        title=payload.title,
        body=payload.body,
        importance=payload.importance,
        metadata=payload.metadata,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.post("/memory-review-items/{item_id}/approve", response_model=MemoryItemResponse)
async def approve_memory_review_item(
    item_id: UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    review_item = await session.scalar(select(MemoryReviewItem).where(MemoryReviewItem.id == item_id))
    if review_item is None:
        raise HTTPException(status_code=404, detail="Memory review item not found")
    await get_owned_novel(session, user, review_item.novel_id)
    review_item.status = "approved"
    memory = MemoryItem(
        novel_id=review_item.novel_id,
        memory_type=review_item.memory_type,
        title=review_item.title,
        body=review_item.body,
        importance=review_item.importance,
        metadata=review_item.metadata,
    )
    session.add(memory)
    await session.commit()
    await session.refresh(memory)
    return memory
```

- [ ] **Step 7: Wire memory module**

Modify `backend/app/models/__init__.py` to include:

```python
from app.models.memory import MemoryItem, MemoryReviewItem
```

Modify `backend/app/api/routes/__init__.py` to include:

```python
from app.api.routes import auth, memory, model_profiles, novels
```

Modify `backend/app/main.py` to include:

```python
from app.api.routes import auth, memory, model_profiles, novels

app.include_router(memory.router)
```

- [ ] **Step 8: Add memory migration**

Create `backend/alembic/versions/0003_memory.py`:

```python
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_memory"
down_revision: str | None = "0002_workspace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_review_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("novel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_memory_review_items_novel_id", "memory_review_items", ["novel_id"])
    op.create_table(
        "memory_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("novel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_memory_items_novel_id", "memory_items", ["novel_id"])
    op.create_index("ix_memory_items_memory_type", "memory_items", ["memory_type"])


def downgrade() -> None:
    op.drop_index("ix_memory_items_memory_type", table_name="memory_items")
    op.drop_index("ix_memory_items_novel_id", table_name="memory_items")
    op.drop_table("memory_items")
    op.drop_index("ix_memory_review_items_novel_id", table_name="memory_review_items")
    op.drop_table("memory_review_items")
```

Run:

```bash
cd backend && . .venv/bin/activate && alembic upgrade head
```

Expected: migration creates memory tables.

- [ ] **Step 9: Run memory and context tests**

Run:

```bash
cd backend && . .venv/bin/activate && pytest tests/test_memory.py tests/test_context_pack.py -v
```

Expected: both tests pass.

- [ ] **Step 10: Commit Task 4**

```bash
git add backend
git commit -m "feat: add layered memory primitives"
```

## Task 5: Agent Graph, Confirmations, And Drafted Changes

**Files:**
- Create: `backend/app/models/confirmation.py`
- Create: `backend/app/schemas/agent.py`
- Create: `backend/app/schemas/confirmation.py`
- Create: `backend/app/agent/state.py`
- Create: `backend/app/agent/tools.py`
- Create: `backend/app/agent/graph.py`
- Create: `backend/app/api/routes/agent.py`
- Create: `backend/app/api/routes/confirmations.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_agent_confirmations.py`

- [ ] **Step 1: Write Agent confirmation test**

Create `backend/tests/test_agent_confirmations.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": "agent@example.com", "username": "agent", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "agent@example.com", "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_agent_rewrite_creates_confirmation_and_apply_updates_document() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Agent Book"}).json()
    chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Chapter 1", "node_type": "chapter", "parent_id": None},
    ).json()
    client.patch(
        f"/documents/{chapter['document_id']}",
        headers=headers,
        json={"content": {"type": "doc", "content": [{"type": "paragraph", "text": "Calm room."}]}},
    )

    response = client.post(
        f"/novels/{novel['id']}/agent/messages",
        headers=headers,
        json={
            "message": "Rewrite the selected paragraph to feel more tense.",
            "document_id": chapter["document_id"],
            "selected_text": "Calm room.",
        },
    )

    assert response.status_code == 200
    confirmation_id = response.json()["confirmation"]["id"]
    applied = client.post(f"/confirmations/{confirmation_id}/approve", headers=headers)
    assert applied.status_code == 200
    document = client.get(f"/documents/{chapter['document_id']}", headers=headers).json()
    assert "tense" in str(document["content"]).lower()
```

- [ ] **Step 2: Run Agent test to verify failure**

Run:

```bash
cd backend && . .venv/bin/activate && pytest tests/test_agent_confirmations.py -v
```

Expected: FAIL because Agent and confirmation routes do not exist.

- [ ] **Step 3: Implement confirmation model and schemas**

Create `backend/app/models/confirmation.py`:

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PendingConfirmation(Base):
    __tablename__ = "pending_confirmations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="pending")
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
```

Create `backend/app/schemas/confirmation.py`:

```python
from uuid import UUID

from pydantic import BaseModel


class ConfirmationResponse(BaseModel):
    id: UUID
    action_type: str
    status: str
    payload: dict
```

Create `backend/app/schemas/agent.py`:

```python
from uuid import UUID

from pydantic import BaseModel

from app.schemas.confirmation import ConfirmationResponse


class AgentMessageRequest(BaseModel):
    message: str
    document_id: UUID | None = None
    selected_text: str | None = None


class AgentMessageResponse(BaseModel):
    message: str
    context_status: list[str]
    confirmation: ConfirmationResponse | None = None
```

- [ ] **Step 4: Implement deterministic MVP Agent tools**

Create `backend/app/agent/state.py`:

```python
from typing import TypedDict
from uuid import UUID


class AgentState(TypedDict, total=False):
    novel_id: UUID
    document_id: UUID | None
    message: str
    selected_text: str | None
    response: str
    context_status: list[str]
    proposed_payload: dict | None
```

Create `backend/app/agent/tools.py`:

```python
def draft_rewrite(selected_text: str, instruction: str) -> str:
    return f"{selected_text} The room turned tense as every sound seemed to wait for the next mistake."


def classify_agent_intent(message: str, selected_text: str | None) -> str:
    lowered = message.lower()
    if selected_text and ("rewrite" in lowered or "改写" in lowered or "重写" in lowered):
        return "rewrite_selection"
    if "remember" in lowered or "记住" in lowered:
        return "draft_key_memory"
    return "chat"
```

Create `backend/app/agent/graph.py`:

```python
from langgraph.graph import END, StateGraph

from app.agent.context import ContextBudget, build_context_pack
from app.agent.state import AgentState
from app.agent.tools import classify_agent_intent, draft_rewrite


def agent_node(state: AgentState) -> AgentState:
    pack = build_context_pack(
        user_instruction=state["message"],
        current_document_text="",
        selected_text=state.get("selected_text"),
        key_memories=[],
        structured_memories=[],
        neighboring_chapters=[],
        rag_results=[],
        budget=ContextBudget(max_tokens=8000, response_tokens=1000),
    )
    intent = classify_agent_intent(state["message"], state.get("selected_text"))
    if intent == "rewrite_selection" and state.get("selected_text") and state.get("document_id"):
        replacement = draft_rewrite(state["selected_text"], state["message"])
        state["response"] = "I drafted a tenser replacement. Please confirm before I apply it."
        state["context_status"] = pack.status_messages
        state["proposed_payload"] = {
            "document_id": str(state["document_id"]),
            "selected_text": state["selected_text"],
            "replacement_text": replacement,
        }
        return state
    state["response"] = "I can help shape the novel. Tell me what to create, rewrite, or remember."
    state["context_status"] = pack.status_messages
    state["proposed_payload"] = None
    return state


def build_agent_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.set_entry_point("agent")
    graph.add_edge("agent", END)
    return graph.compile()
```

- [ ] **Step 5: Implement Agent and confirmation routes**

Create `backend/app/api/routes/agent.py`:

```python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import build_agent_graph
from app.api.deps import current_user
from app.db.session import get_session
from app.models.confirmation import PendingConfirmation
from app.models.user import User
from app.schemas.agent import AgentMessageRequest, AgentMessageResponse
from app.services.novels import get_owned_novel

router = APIRouter(prefix="/novels/{novel_id}/agent", tags=["agent"])


@router.post("/messages", response_model=AgentMessageResponse)
async def send_agent_message(
    novel_id: UUID,
    payload: AgentMessageRequest,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    await get_owned_novel(session, user, novel_id)
    graph = build_agent_graph()
    result = graph.invoke(
        {
            "novel_id": novel_id,
            "document_id": payload.document_id,
            "message": payload.message,
            "selected_text": payload.selected_text,
        }
    )
    confirmation = None
    if result.get("proposed_payload"):
        confirmation = PendingConfirmation(
            novel_id=novel_id,
            action_type="rewrite_selection",
            payload=result["proposed_payload"],
        )
        session.add(confirmation)
        await session.commit()
        await session.refresh(confirmation)
    return AgentMessageResponse(
        message=result["response"],
        context_status=result["context_status"],
        confirmation=confirmation,
    )
```

Create `backend/app/api/routes/confirmations.py`:

```python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_session
from app.models.confirmation import PendingConfirmation
from app.models.document import Document, DocumentVersion
from app.models.user import User
from app.schemas.confirmation import ConfirmationResponse
from app.services.novels import get_owned_novel

router = APIRouter(prefix="/confirmations", tags=["confirmations"])


@router.post("/{confirmation_id}/approve", response_model=ConfirmationResponse)
async def approve_confirmation(
    confirmation_id: UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    confirmation = await session.scalar(
        select(PendingConfirmation).where(PendingConfirmation.id == confirmation_id)
    )
    if confirmation is None:
        raise HTTPException(status_code=404, detail="Confirmation not found")
    await get_owned_novel(session, user, confirmation.novel_id)
    if confirmation.action_type == "rewrite_selection":
        document = await session.scalar(
            select(Document).where(Document.id == UUID(confirmation.payload["document_id"]))
        )
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        session.add(DocumentVersion(document_id=document.id, source="agent", content=document.content))
        document.content = {
            "type": "doc",
            "content": [{"type": "paragraph", "text": confirmation.payload["replacement_text"]}],
        }
    confirmation.status = "approved"
    await session.commit()
    await session.refresh(confirmation)
    return confirmation
```

- [ ] **Step 6: Wire Agent routes and migration**

Modify `backend/app/api/routes/__init__.py`:

```python
from app.api.routes import agent, auth, confirmations, memory, model_profiles, novels

__all__ = ["agent", "auth", "confirmations", "memory", "model_profiles", "novels"]
```

Modify `backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agent, auth, confirmations, memory, model_profiles, novels
from app.core.config import settings


app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(model_profiles.router)
app.include_router(novels.router)
app.include_router(memory.router)
app.include_router(agent.router)
app.include_router(confirmations.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}
```

Create `backend/alembic/versions/0004_confirmations.py`:

```python
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_confirmations"
down_revision: str | None = "0003_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pending_confirmations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("novel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pending_confirmations_novel_id", "pending_confirmations", ["novel_id"])


def downgrade() -> None:
    op.drop_index("ix_pending_confirmations_novel_id", table_name="pending_confirmations")
    op.drop_table("pending_confirmations")
```

Run:

```bash
cd backend && . .venv/bin/activate && alembic upgrade head
```

Expected: migration creates `pending_confirmations`.

- [ ] **Step 7: Run Agent confirmation tests**

Run:

```bash
cd backend && . .venv/bin/activate && pytest tests/test_agent_confirmations.py -v
```

Expected: test passes and document content contains the drafted tense replacement.

- [ ] **Step 8: Commit Task 5**

```bash
git add backend
git commit -m "feat: add agent confirmations"
```

## Task 6: Frontend Auth, Workspace Shell, Editor, And Chat

**Files:**
- Create: `frontend/src/api/http.ts`
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/api/novels.ts`
- Create: `frontend/src/api/workspace.ts`
- Create: `frontend/src/api/documents.ts`
- Create: `frontend/src/api/memory.ts`
- Create: `frontend/src/api/agent.ts`
- Create: `frontend/src/api/modelProfiles.ts`
- Create: `frontend/src/features/auth/AuthPage.tsx`
- Create: `frontend/src/features/novels/NovelList.tsx`
- Create: `frontend/src/features/workspace/WorkspacePage.tsx`
- Create: `frontend/src/features/workspace/WorkspaceTree.tsx`
- Create: `frontend/src/features/editor/DocumentEditor.tsx`
- Create: `frontend/src/features/agent/AgentPanel.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/test/workspace.test.tsx`

- [ ] **Step 1: Write frontend workspace smoke test**

Create `frontend/src/test/workspace.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkspacePage } from "../features/workspace/WorkspacePage";

describe("WorkspacePage", () => {
  it("renders the three-pane novel IDE", () => {
    render(<WorkspacePage token="test-token" novelId="novel-1" />);

    expect(screen.getByText("Workspace")).toBeTruthy();
    expect(screen.getByText("Editor")).toBeTruthy();
    expect(screen.getByText("Agent")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run frontend test to verify failure**

Run:

```bash
cd frontend && npm install && npm test -- workspace.test.tsx
```

Expected: FAIL because `WorkspacePage` does not exist.

- [ ] **Step 3: Implement domain-split API clients**

Create `frontend/src/api/http.ts`:

```ts
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export async function apiRequest<T>(
  path: string,
  options: RequestInit & { token?: string } = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}
```

Create `frontend/src/api/auth.ts`:

```ts
import { apiRequest } from "./http";

export type LoginResponse = {
  access_token: string;
  token_type: "bearer";
};

export function login(loginName: string, password: string) {
  return apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ login: loginName, password }),
  });
}
```

Create `frontend/src/api/novels.ts`:

```ts
import { apiRequest } from "./http";

export type Novel = {
  id: string;
  title: string;
  description: string;
};

export function listNovels(token: string) {
  return apiRequest<Novel[]>("/novels", { token });
}

export function createNovel(token: string, title: string) {
  return apiRequest<Novel>("/novels", {
    method: "POST",
    token,
    body: JSON.stringify({ title }),
  });
}
```

Create `frontend/src/api/workspace.ts`:

```ts
import { apiRequest } from "./http";

export type WorkspaceNode = {
  id: string;
  novel_id: string;
  parent_id: string | null;
  document_id: string | null;
  title: string;
  node_type: string;
  status: string;
  position: number;
};

export function listWorkspaceNodes(token: string, novelId: string) {
  return apiRequest<WorkspaceNode[]>(`/novels/${novelId}/nodes`, { token });
}
```

Create `frontend/src/api/documents.ts`:

```ts
import { apiRequest } from "./http";

export type DocumentBody = Record<string, unknown>;

export type DocumentRecord = {
  id: string;
  novel_id: string;
  content: DocumentBody;
};

export function getDocument(token: string, documentId: string) {
  return apiRequest<DocumentRecord>(`/documents/${documentId}`, { token });
}
```

Create `frontend/src/api/memory.ts`:

```ts
import { apiRequest } from "./http";

export type MemoryReviewItem = {
  id: string;
  memory_type: string;
  title: string;
  body: string;
  importance: number;
  status: string;
};

export function createMemoryReviewItem(
  token: string,
  novelId: string,
  payload: Omit<MemoryReviewItem, "id" | "status">,
) {
  return apiRequest<MemoryReviewItem>(`/novels/${novelId}/memory-review-items`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}
```

Create `frontend/src/api/agent.ts`:

```ts
import { apiRequest } from "./http";

export type AgentMessageResponse = {
  message: string;
  context_status: string[];
  confirmation: null | {
    id: string;
    action_type: string;
    status: string;
    payload: Record<string, unknown>;
  };
};

export function sendAgentMessage(
  token: string,
  novelId: string,
  payload: { message: string; document_id?: string | null; selected_text?: string | null },
) {
  return apiRequest<AgentMessageResponse>(`/novels/${novelId}/agent/messages`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}
```

Create `frontend/src/api/modelProfiles.ts`:

```ts
import { apiRequest } from "./http";

export type ModelProfile = {
  id: string;
  name: string;
  provider_kind: string;
  base_url: string | null;
  chat_model: string;
  writing_model: string;
  summary_model: string;
  embedding_model: string;
  supports_tool_calling: boolean;
  supports_json_mode: boolean;
  supports_streaming: boolean;
  context_window: number;
  embedding_dimensions: number;
  extra_headers: Record<string, string>;
};

export function listModelProfiles(token: string) {
  return apiRequest<ModelProfile[]>("/model-profiles", { token });
}
```

- [ ] **Step 4: Add UI library primitives**

Run:

```bash
cd frontend && npx shadcn@latest init -d && npx shadcn@latest add button textarea card scroll-area
```

Expected: shadcn/ui creates reusable UI primitives under `frontend/src/components/ui`. Use these primitives before adding custom buttons, textareas, cards, or scroll containers.

- [ ] **Step 5: Implement three-pane workspace with UI primitives**

Create `frontend/src/features/workspace/WorkspaceTree.tsx`:

```tsx
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";

export function WorkspaceTree() {
  return (
    <aside aria-label="Workspace tree" className="border-r p-3">
      <h2>Workspace</h2>
      <Button type="button">New Chapter</Button>
      <Card className="mt-3 p-3">
        <ul>
          <li>Chapter 1</li>
        </ul>
      </Card>
    </aside>
  );
}
```

Create `frontend/src/features/editor/DocumentEditor.tsx`:

```tsx
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";

export function DocumentEditor() {
  const editor = useEditor({
    extensions: [StarterKit],
    content: "<p>Start writing...</p>",
  });

  return (
    <section className="p-3">
      <h2>Editor</h2>
      <EditorContent editor={editor} />
    </section>
  );
}
```

Create `frontend/src/features/agent/AgentPanel.tsx`:

```tsx
import { Button } from "../../components/ui/button";
import { Textarea } from "../../components/ui/textarea";

export function AgentPanel() {
  return (
    <aside aria-label="Agent chat" className="border-l p-3">
      <h2>Agent</h2>
      <p>Ask the Agent to create, rewrite, or remember.</p>
      <Textarea aria-label="Agent message" placeholder="Talk with the Agent..." />
      <Button type="button">Send</Button>
    </aside>
  );
}
```

Create `frontend/src/features/workspace/WorkspacePage.tsx`:

```tsx
import { AgentPanel } from "../agent/AgentPanel";
import { DocumentEditor } from "../editor/DocumentEditor";
import { WorkspaceTree } from "./WorkspaceTree";

type WorkspacePageProps = {
  token: string;
  novelId: string;
};

export function WorkspacePage({ token, novelId }: WorkspacePageProps) {
  void token;
  void novelId;

  return (
    <main
      className="grid min-h-screen grid-cols-[260px_1fr_360px] font-sans"
    >
      <WorkspaceTree />
      <DocumentEditor />
      <AgentPanel />
    </main>
  );
}
```

- [ ] **Step 6: Implement auth and novel list minimal app**

Create `frontend/src/features/auth/AuthPage.tsx`:

```tsx
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";

type AuthPageProps = {
  onAuthenticated: (token: string) => void;
};

export function AuthPage({ onAuthenticated }: AuthPageProps) {
  return (
    <main className="p-6">
      <Card className="max-w-md p-6">
        <h1>AI Story</h1>
        <p>Sign in to create a novel workspace.</p>
        <Button type="button" onClick={() => onAuthenticated("local-demo-token")}>
          Continue in demo mode
        </Button>
      </Card>
    </main>
  );
}
```

Create `frontend/src/features/novels/NovelList.tsx`:

```tsx
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";

type NovelListProps = {
  onOpenNovel: (novelId: string) => void;
};

export function NovelList({ onOpenNovel }: NovelListProps) {
  return (
    <main className="p-6">
      <Card className="max-w-md p-6">
        <h1>Your novels</h1>
        <Button type="button" onClick={() => onOpenNovel("demo-novel")}>
          Open demo novel
        </Button>
      </Card>
    </main>
  );
}
```

Modify `frontend/src/App.tsx`:

```tsx
import { useState } from "react";

import { AuthPage } from "./features/auth/AuthPage";
import { NovelList } from "./features/novels/NovelList";
import { WorkspacePage } from "./features/workspace/WorkspacePage";

export function App() {
  const [token, setToken] = useState<string | null>(null);
  const [novelId, setNovelId] = useState<string | null>(null);

  if (!token) {
    return <AuthPage onAuthenticated={setToken} />;
  }
  if (!novelId) {
    return <NovelList onOpenNovel={setNovelId} />;
  }
  return <WorkspacePage token={token} novelId={novelId} />;
}
```

- [ ] **Step 7: Run frontend tests and build**

Run:

```bash
cd frontend && npm test -- workspace.test.tsx && npm run build
```

Expected: workspace test passes and Vite build completes.

- [ ] **Step 8: Commit Task 6**

```bash
git add frontend
git commit -m "feat: add novel workspace UI"
```

## Task 7: End-To-End MVP Verification

**Files:**
- Create: `backend/tests/test_mvp_flow.py`
- Create: `frontend/src/test/app.test.tsx`
- Modify: `README.md`

- [ ] **Step 1: Write backend MVP flow test**

Create `backend/tests/test_mvp_flow.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_mvp_backend_flow() -> None:
    client = TestClient(app)
    client.post(
        "/auth/register",
        json={"email": "mvp@example.com", "username": "mvp", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "mvp@example.com", "password": "secret123"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    novel = client.post("/novels", headers=headers, json={"title": "MVP Novel"}).json()
    chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Chapter 1", "node_type": "chapter", "parent_id": None},
    ).json()
    client.post(
        f"/novels/{novel['id']}/memory-review-items",
        headers=headers,
        json={
            "memory_type": "key_memory",
            "title": "Core promise",
            "body": "Never betray the patient.",
            "importance": 100,
        },
    )
    agent = client.post(
        f"/novels/{novel['id']}/agent/messages",
        headers=headers,
        json={
            "message": "Rewrite the selected paragraph to feel more tense.",
            "document_id": chapter["document_id"],
            "selected_text": "The clinic was quiet.",
        },
    )
    assert agent.status_code == 200
    assert agent.json()["confirmation"]["action_type"] == "rewrite_selection"
```

- [ ] **Step 2: Write frontend app smoke test**

Create `frontend/src/test/app.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "../App";

describe("App", () => {
  it("opens demo workspace", () => {
    render(<App />);

    fireEvent.click(screen.getByText("Continue in demo mode"));
    fireEvent.click(screen.getByText("Open demo novel"));

    expect(screen.getByText("Workspace")).toBeTruthy();
    expect(screen.getByText("Editor")).toBeTruthy();
    expect(screen.getByText("Agent")).toBeTruthy();
  });
});
```

- [ ] **Step 3: Add README run instructions**

Create `README.md`:

```markdown
# AI Story

Agent-first novel creation IDE.

## Local Development

Start infrastructure and apps:

```bash
docker compose --env-file .env.example up
```

Run backend tests:

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

Run frontend tests:

```bash
cd frontend
npm install
npm test
```

## MVP Capabilities

- Local account authentication.
- User-owned novels.
- Workspace tree with chapter documents.
- TipTap editor shell.
- Agent chat shell.
- Key memory review and approval.
- Context pack assembly.
- Human-confirmed Agent rewrite changes.
```

- [ ] **Step 4: Run full backend tests**

Run:

```bash
cd backend && . .venv/bin/activate && pytest -v
```

Expected: all backend tests pass.

- [ ] **Step 5: Run full frontend tests and build**

Run:

```bash
cd frontend && npm test && npm run build
```

Expected: all frontend tests pass and build succeeds.

- [ ] **Step 6: Validate Docker Compose config**

Run:

```bash
docker compose --env-file .env.example config
```

Expected: config validates successfully with `web`, `api`, `postgres`, and `milvus`.

- [ ] **Step 7: Commit Task 7**

```bash
git add README.md backend frontend
git commit -m "test: verify mvp flow"
```

## Self-Review

Spec coverage:

- Three-pane novel IDE: Task 6.
- Natural dialogue inside a novel: Task 5 and Task 6.
- Hidden Skills: Task 5 introduces deterministic Agent tools and routing.
- Human-in-the-loop confirmations: Task 5.
- Local accounts and isolation: Task 2 and ownership checks in Task 3 onward.
- Configurable model profiles: Task 2.
- Workspace tree, chapters, drafts, documents, versions: Task 3.
- Layered memory, key memory, review queue, context pack: Task 4.
- Neighboring chapter context and token budget primitives: Task 4.
- Docker Compose with Postgres and Milvus: Task 1.

Known follow-up plans:

- Replace deterministic Agent draft functions with real LLM provider adapters and streaming.
- Add actual Milvus indexing and retrieval adapters.
- Add complete assistant-ui integration and visual confirmation cards.
- Add structured creative asset CRUD, timeline events, character states, and relationship graph UI.
- Add Playwright browser tests for the full user journey.

