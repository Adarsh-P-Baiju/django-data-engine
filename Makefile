.PHONY: help up down down-volumes restart restart-workers build \
        logs logs-web logs-worker logs-db \
        shell dbshell redis-cli \
        makemigrations migrate check migrate-check superuser collectstatic \
        showmigrations squashmigrations flush dumpdata loaddata \
        pip-install pip-freeze \
        test check-deploy \
        format lint ruff ruff-fix

# Default
help:
	@echo "=================================================================="
	@echo "  Django Data Engine — Makefile Commands"
	@echo "=================================================================="
	@echo ""
	@echo "  --- Docker ---"
	@echo "  make up                - Start all containers"
	@echo "  make down              - Stop all containers"
	@echo "  make down-volumes      - ⚠️ Stop containers + wipe all volumes"
	@echo "  make restart           - Full cluster restart"
	@echo "  make restart-workers   - Soft restart Celery workers only"
	@echo "  make build             - Rebuild images + start"
	@echo ""
	@echo "  --- Logs ---"
	@echo "  make logs              - Tail all container logs"
	@echo "  make logs-web          - Django API logs"
	@echo "  make logs-worker       - Celery + Flower logs"
	@echo "  make logs-db           - PostgreSQL logs"
	@echo ""
	@echo "  --- Shells ---"
	@echo "  make shell             - Bash inside web container"
	@echo "  make dbshell           - PostgreSQL interactive shell"
	@echo "  make redis-cli         - Redis interactive CLI"
	@echo ""
	@echo "  --- Django Core ---"
	@echo "  make makemigrations    - Generate new migrations"
	@echo "  make migrate           - Apply database migrations"
	@echo "  make check             - Run Django system checks"
	@echo "  make check-deploy      - Run production deployment checks"
	@echo "  make migrate-check     - Verify no missing migrations exist"
	@echo "  make showmigrations    - List all migrations and their status"
	@echo "  make squashmigrations  - Squash an app's migrations (set APP=myapp NUM=0001)"
	@echo "  make flush             - ⚠️ Wipe all data from the database"
	@echo "  make dumpdata          - Dump all DB data to fixtures/db.json"
	@echo "  make loaddata          - Load fixtures/db.json into the DB"
	@echo "  make superuser         - Create a Django admin user"
	@echo "  make collectstatic     - Collect static files"
	@echo ""
	@echo "  --- Python Packages ---"
	@echo "  make pip-install       - Install requirements.txt into container"
	@echo "  make pip-freeze        - Write container pip freeze to requirements.txt"
	@echo ""
	@echo "  --- Code Quality ---"
	@echo "  make test              - Run Django test suite"
	@echo "  make ruff              - Ruff lint check"
	@echo "  make ruff-fix          - Auto-fix all ruff violations"
	@echo "  make format            - Auto-format with black"
	@echo "  make lint              - Flake8 lint check"
	@echo "=================================================================="

# ========================
# Docker Cluster
# ========================
up:
	docker compose up -d

down:
	docker compose down

down-volumes:
	docker compose down -v

restart:
	docker compose down
	docker compose up -d

restart-workers:
	docker compose restart celery_heavy celery_light

build:
	docker compose up -d --build

# ========================
# Logs
# ========================
logs:
	docker compose logs -f

logs-web:
	docker compose logs -f web

logs-worker:
	docker compose logs -f celery_heavy celery_light flower

logs-db:
	docker compose logs -f db

# ========================
# Shells
# ========================
shell:
	docker compose exec web /bin/bash

dbshell:
	docker compose exec db psql -U pguser -d import_db

redis-cli:
	docker compose exec redis redis-cli

# ========================
# Django Core
# ========================
makemigrations:
	docker compose exec web python manage.py makemigrations

migrate:
	docker compose exec web python manage.py migrate

check:
	docker compose exec web python manage.py check

check-deploy:
	docker compose exec web python manage.py check --deploy

migrate-check:
	docker compose exec web python manage.py makemigrations --check --dry-run

showmigrations:
	docker compose exec web python manage.py showmigrations

squashmigrations:
	docker compose exec web python manage.py squashmigrations $(APP) $(NUM)

flush:
	docker compose exec web python manage.py flush --noinput

dumpdata:
	docker compose exec web python manage.py dumpdata --indent 2 > fixtures/db.json

loaddata:
	docker compose exec web python manage.py loaddata fixtures/db.json

superuser:
	docker compose exec web python manage.py createsuperuser

collectstatic:
	docker compose exec web python manage.py collectstatic --noinput

# ========================
# Python Packages
# ========================
pip-install:
	docker compose exec web pip install -r requirements.txt

pip-freeze:
	docker compose exec web pip freeze > requirements.txt

# ========================
# Code Quality
# ========================
test:
	docker compose exec web python manage.py test import_engine

ruff:
	docker compose exec web ruff check .

ruff-fix:
	docker compose exec web ruff check --fix . && docker compose exec web ruff format .

format:
	docker compose exec web black .

lint:
	docker compose exec web flake8 .
