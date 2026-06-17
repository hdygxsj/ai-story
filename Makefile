.PHONY: backend-bootstrap backend-test frontend-test cli-test cli-build test up down db-migrate

backend-bootstrap:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"

backend-test: backend-bootstrap
	cd backend && . .venv/bin/activate && pytest -v

frontend-test:
	cd frontend && npm test

cli-test:
	cd cli && go test ./...

cli-build:
	cd cli && go build ./cmd/ai-story

test: backend-test frontend-test cli-test

up:
	docker compose --env-file .env.example up

down:
	docker compose down

db-migrate:
	./scripts/db-migrate.sh

db-seed:
	./scripts/db-seed.sh
