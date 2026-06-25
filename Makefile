.PHONY: help sync up down build migrate makemigrations superuser test lint fmt shell run logs

help:
	@echo "Local (uv):   make sync | run | test | lint | fmt"
	@echo "Docker:       make up | down | build | logs | migrate | superuser"

# --- Local dev with uv ---
sync:          ## Install/refresh the local virtualenv from uv.lock
	uv sync

run:           ## Run the dev server locally (needs Postgres reachable via DATABASE_URL)
	uv run python manage.py runserver

test:          ## Run the test suite (sqlite in-memory unless DATABASE_URL is set)
	uv run pytest

lint:
	uv run ruff check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

# --- Docker (zero-setup local stack) ---
up:            ## Build if needed and start the full stack at http://localhost:8000
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f web

migrate:
	docker compose run --rm web python manage.py migrate

makemigrations:
	docker compose run --rm web python manage.py makemigrations

superuser:
	docker compose run --rm web python manage.py createsuperuser

shell:
	docker compose run --rm web python manage.py shell
