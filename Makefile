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
