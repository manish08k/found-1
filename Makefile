.PHONY: help dev up down logs migrate worker beat flower shell test lint

help:
	@echo "AutoFlow Dev Commands"
	@echo "  make dev       — start full stack (docker-compose)"
	@echo "  make up        — docker-compose up -d"
	@echo "  make down      — docker-compose down"
	@echo "  make logs      — follow all logs"
	@echo "  make migrate   — run alembic migrations"
	@echo "  make worker    — start celery worker (local)"
	@echo "  make beat      — start celery beat (local)"
	@echo "  make flower    — start flower monitor"
	@echo "  make shell     — python REPL with app context"
	@echo "  make test      — run test suite"
	@echo "  make lint      — ruff + mypy"
	@echo "  make keygen    — generate APP_SECRET_KEY + CREDENTIAL_ENCRYPTION_KEY"

dev: up logs

up:
	docker-compose up -d --build

down:
	docker-compose down

logs:
	docker-compose logs -f

migrate:
	alembic upgrade head

worker:
	celery -A workers.tasks.celery_app worker \
		--loglevel=info \
		--queues=workflows,polling,maintenance \
		--concurrency=4

beat:
	celery -A workers.tasks.celery_app beat \
		--loglevel=info

flower:
	celery -A workers.tasks.celery_app flower \
		--port=5555

api:
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

shell:
	python -c "import asyncio; from storage.database import AsyncSessionLocal; print('DB session ready')"

test:
	pytest tests/ -v --asyncio-mode=auto

lint:
	ruff check . && mypy . --ignore-missing-imports

keygen:
	@python -c "import secrets; \
	print('APP_SECRET_KEY=' + secrets.token_hex(32)); \
	print('CREDENTIAL_ENCRYPTION_KEY=' + secrets.token_hex(16))"
