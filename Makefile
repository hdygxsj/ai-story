.PHONY: backend-bootstrap backend-test frontend-test test up down

backend-bootstrap:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"

backend-test: backend-bootstrap
	cd backend && . .venv/bin/activate && pytest -v

frontend-test:
	cd frontend && npm test

test: backend-test frontend-test

up:
	docker compose --env-file .env.example up

down:
	docker compose down
