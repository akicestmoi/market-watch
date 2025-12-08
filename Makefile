help:
	@echo "Available commands:"
	@echo "  build           - Build the Docker image"
	@echo "  install         - Install dependencies"
	@echo "  lint            - Lint the code"
	@echo "  flake8          - Run Flake8"
	@echo "  pyright         - Run Pyright"
	@echo "  start           - Start the application"
	@echo "  stop            - Stop all containers"
	@echo "  restart         - Restart all containers"
	@echo "  logs            - Show logs from all containers"
	@echo "  logs-webapp     - Show logs from webapp container"
	@echo "  shell           - Open a shell in the webapp container"
	@echo "  makemigrations  - Prepare database migrations"
	@echo "  migrate         - Run database migrations"
	@echo "  collectstatic   - Collect static files"
	@echo "  celery-beat     - View Celery beat scheduler logs"
	@echo "  celery-worker   - View Celery worker logs"
	@echo "  flower          - View Celery Flower monitoring logs"
	@echo "  test            - Run all tests (pytest)"
	@echo "  clean           - Clean up Docker resources"
	@echo "  db-export       - Export database to SQL file"
	@echo "  db-import       - Import database from SQL file (requires SQL_FILE=path)"
	@echo "  trigger-task    - Manually trigger a scheduled Celery task (requires TASK=name)"
	@echo "  test-coverage   - Run tests with coverage report (HTML + terminal)"
	@echo "  test-app        - Run tests for a specific app (requires APP=name, uses pytest)"

DOCKER_COMPOSE = docker compose -f scripts/docker/docker-compose.yml

# Helper variable to run commands in temporary container
RUN_TMP = $(DOCKER_COMPOSE) run --rm --no-deps webapp

# Install dependencies
install:
	$(DOCKER_COMPOSE) exec webapp pip install -r requirements.txt
	$(DOCKER_COMPOSE) exec webapp npm install

# Lint
lint:
	$(DOCKER_COMPOSE) exec webapp black . & isort .
	$(DOCKER_COMPOSE) exec webapp npm run lint:all

# Flake8
flake8:
	$(DOCKER_COMPOSE) exec webapp flake8

# Pyright
pyright:
	$(DOCKER_COMPOSE) exec webapp pyright

# Build the Docker image
build:
	$(DOCKER_COMPOSE) build

# Start application
start:
	$(DOCKER_COMPOSE) up --build

# Stop all containers
stop:
	$(DOCKER_COMPOSE) down

# Restart all containers
restart:
	$(DOCKER_COMPOSE) restart

# Show logs from all containers
logs:
	$(DOCKER_COMPOSE) logs -f

# Show logs from web container
logs-webapp:
	$(DOCKER_COMPOSE) logs -f webapp


# Open a shell in the web container
shell:
	$(DOCKER_COMPOSE) exec webapp bash

# Prepare database migrations
makemigrations:
	$(DOCKER_COMPOSE) exec webapp python manage.py makemigrations

# Run database migrations
migrate:
	$(DOCKER_COMPOSE) exec webapp python manage.py migrate

# Collect static files
collectstatic:
	$(DOCKER_COMPOSE) exec webapp python manage.py collectstatic --noinput

# Run tests
# $(DOCKER_COMPOSE) exec webapp python -m pytest central_banks_overview/tests/services/test_cb_data_services.py -vv --exitfirst
# $(DOCKER_COMPOSE) exec webapp python -m pytest -vv
test:
	$(DOCKER_COMPOSE) exec webapp python -m pytest -vv

# Run tests with coverage report
test-coverage:
	$(DOCKER_COMPOSE) exec webapp python -m pytest --cov --cov-report=term --cov-report=html

# Run tests for a specific app
test-app:
	$(if $(APP),,$(error APP is required. Example: make test-app APP=market_overview))
	$(DOCKER_COMPOSE) exec webapp python -m pytest $(APP)/tests

# Clean up Docker resources
clean:
	$(DOCKER_COMPOSE) down -v
	docker system prune -f

# Clean and restart
reset: stop clean start
	@echo "Application reset complete. Access the application at http://localhost:8000"

# Starts a Celery beat scheduler process inside container and schedules periodic tasks
celery-beat:
	$(DOCKER_COMPOSE) logs -f celery-beat

# Starts a Celery worker process inside container and processes tasks from the Redis queue
celery-worker:
	$(DOCKER_COMPOSE) logs -f celery-worker

# View Celery Flower monitoring interface logs
flower:
	$(DOCKER_COMPOSE) logs -f flower

# Export database
db-export:
	@if $(DOCKER_COMPOSE) ps webapp 2>/dev/null | grep -q "Up"; then \
		$(DOCKER_COMPOSE) exec webapp python scripts/db_management/export_db.py; \
	else \
		echo "Container not running, starting temporary container..."; \
		$(RUN_TMP) python scripts/db_management/export_db.py; \
	fi

# Import database
db-import:
	$(if $(SQL_FILE),,$(error SQL_FILE is required. Example: make db-import SQL_FILE=db_backup.sql))
	@if $(DOCKER_COMPOSE) ps webapp 2>/dev/null | grep -q "Up"; then \
		$(DOCKER_COMPOSE) exec webapp python scripts/db_management/import_db.py $(SQL_FILE) --no-confirm; \
	else \
		echo "Container not running, starting temporary container..."; \
		$(RUN_TMP) python scripts/db_management/import_db.py $(SQL_FILE) --no-confirm; \
	fi

# Trigger a scheduled Celery task
trigger-task:
	$(if $(TASK),,$(error TASK is required. Example: make trigger-task TASK=scheduled_market_data_ingestion))
	@$(DOCKER_COMPOSE) exec webapp python manage.py trigger_task $(TASK) $(if $(ASYNC),--async,) || $(RUN_TMP) python manage.py trigger_task $(TASK) $(if $(ASYNC),--async,)

.PHONY: help install lint flake8 pyright build start stop restart logs logs-webapp shell makemigrations migrate collectstatic test test-coverage test-app clean reset celery-beat celery-worker flower db-export db-import trigger-task
