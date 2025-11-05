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
	@echo "  test            - Run tests"
	@echo "  clean           - Clean up Docker resources"
	@echo "  db-export       - Export database to SQL file"
	@echo "  db-import       - Import database from SQL file (requires SQL_FILE=path)"

DOCKER_COMPOSE = docker compose -f scripts/docker/docker-compose.yml

# Install dependencies
install:
	$(DOCKER_COMPOSE) exec webapp npm install
	$(DOCKER_COMPOSE) exec webapp pip install -r requirements.txt

.run-tmp:
	$(DOCKER_COMPOSE) run --rm --no-deps webapp $(CMD)

# Lint
lint:
	$(DOCKER_COMPOSE) exec webapp npm run lint:all
	$(DOCKER_COMPOSE) exec webapp black . & isort .

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
test:
	$(DOCKER_COMPOSE) exec webapp python manage.py test

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

# Export database
db-export:
	@if $(DOCKER_COMPOSE) ps webapp 2>/dev/null | grep -q "Up"; then \
		$(DOCKER_COMPOSE) exec webapp python scripts/db_management/export_db.py; \
	else \
		echo "Container not running, starting temporary container..."; \
		.run-tmp python scripts/db_management/export_db.py; \
	fi

# Import database
db-import:
	@echo "Usage: make db-import SQL_FILE=path/to/backup.sql"
	@if [ -z "$(SQL_FILE)" ]; then \
		echo "ERROR: SQL_FILE is required. Example: make db-import SQL_FILE=db_backup.sql"; \
		exit 1; \
	fi
	@if $(DOCKER_COMPOSE) ps webapp 2>/dev/null | grep -q "Up"; then \
		$(DOCKER_COMPOSE) exec webapp python scripts/db_management/import_db.py $(SQL_FILE); \
	else \
		echo "Container not running, starting temporary container..."; \
		.run-tmp python scripts/db_management/import_db.py $(SQL_FILE); \
	fi

.PHONY: help install lint flake8 pyright build start stop restart logs logs-webapp shell makemigrations migrate collectstatic test clean reset celery-beat celery-worker db-export db-import
