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
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

Run frontend tests:

```bash
cd frontend
npm ci
npm test
```

## MVP Capabilities

- Local account authentication.
- User-owned novels.
- Workspace tree with chapter documents.
- Editor shell with selected text handoff.
- Agent chat shell.
- Key memory review and approval.
- Context pack assembly.
- Human-confirmed Agent rewrite changes.
- Docker Compose for Postgres, Milvus, API, and web.
