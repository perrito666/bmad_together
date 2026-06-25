.PHONY: help up down build migrate makemigrations superuser test lint fmt shell run

help:
	@echo "Targets: up down build migrate makemigrations superuser test lint fmt run"

up:            ## Start the stack (Postgres + web)
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

migrate:
	docker compose run --rm web python manage.py migrate

makemigrations:
	docker compose run --rm web python manage.py makemigrations

superuser:
	docker compose run --rm web python manage.py createsuperuser

run:           ## Run the dev server locally (expects a venv + Postgres)
	python manage.py runserver

test:          ## Run the test suite (sqlite in-memory unless DATABASE_URL is set)
	pytest

lint:
	ruff check .

fmt:
	ruff format .
	ruff check --fix .

shell:
	docker compose run --rm web python manage.py shell
