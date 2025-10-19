help:
	@echo "Available commands:"
	@echo "  build           - Build the Docker image"
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
	@echo "  celery-flower   - Start Celery monitoring (Flower)"
	@echo "  test            - Run tests"
	@echo "  clean           - Clean up Docker resources"

# Build the Docker image
build:
	docker compose build

# Start application
start:
	docker compose up --build

# Stop all containers
stop:
	docker compose down

# Restart all containers
restart:
	docker compose restart

# Show logs from all containers
logs:
	docker compose logs -f

# Show logs from web container
logs-webapp:
	docker compose logs -f webapp


# Open a shell in the web container
shell:
	docker compose exec webapp bash

# Prepare database migrations
makemigrations:
	docker compose exec webapp python manage.py makemigrations

# Run database migrations
migrate:
	docker compose exec webapp python manage.py migrate

# Collect static files
collectstatic:
	docker compose exec webapp python manage.py collectstatic --noinput

# Run tests
test:
	docker compose exec webapp python manage.py test

# Clean up Docker resources
clean:
	docker compose down -v
	docker system prune -f

# Clean and restart
reset: stop clean start
	@echo "Application reset complete. Access the application at http://localhost:8000"

# Starts a Celery beat scheduler process inside container and schedules periodic tasks
celery-beat:
	docker compose logs -f celery-beat

# Starts a Celery worker process inside container and processes tasks from the Redis queue
celery-worker:
	docker compose logs -f celery-worker

# Starts a Celery monitoring interface (Flower) inside container for monitoring and managing tasks
celery-flower:
	docker compose exec webapp celery -A core flower --port=5555

.PHONY: help build start stop restart logs logs-webapp shell makemigrations migrate collectstatic test clean reset celery-beat celery-worker celery-flower
