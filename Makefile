.PHONY: up down build logs shell migrate test test-unit test-integration test-e2e lint fmt seed

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f web asgi

shell:
	docker compose exec web python manage.py shell

migrate:
	docker compose exec web python manage.py migrate

test: test-unit test-integration

test-unit:
	uv run pytest backend/tests/unit -v

test-integration:
	uv run pytest backend/tests/integration -v

test-e2e:
	uv run pytest backend/tests/e2e -v -m e2e

lint:
	uv run ruff check backend/

fmt:
	uv run ruff format backend/

seed:
	docker compose exec web python manage.py seed_demo
