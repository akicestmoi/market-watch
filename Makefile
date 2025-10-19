help:
	@echo "Available commands:"
	@echo "  build           - Build the Docker image"
	@echo "  start           - Start the application"
	@echo "  stop            - Stop all containers"
	@echo "  restart         - Restart all containers"
	@echo "  logs            - Show logs from all containers"
	@echo "  logs-webapp     - Show logs from webapp container"
	@echo "  logs-db         - Show logs from database container"
	@echo "  shell           - Open a shell in the webapp container"
	@echo "  makemigrations  - Prepare database migrations"
	@echo "  migrate         - Run database migrations"
	@echo "  collectstatic   - Collect static files"
	@echo "  test            - Run tests"
	@echo "  clean           - Clean up Docker resources"
	@echo "  reset           - Reset the database and restart"

# Build the Docker image
build:
	docker-compose build

# Start application
start:
	docker-compose up --build

# Stop all containers
stop:
	docker-compose down

# Restart all containers
restart:
	docker-compose restart

# Show logs from all containers
logs:
	docker-compose logs -f

# Show logs from web container
logs-webapp:
	docker-compose logs -f webapp

# Show logs from database container
logs-db:
	docker-compose logs -f db

# Open a shell in the web container
shell:
	docker-compose exec webapp bash

# Prepare database migrations
makemigrations:
	docker-compose exec webapp python manage.py makemigrations

# Run database migrations
migrate:
	docker-compose exec webapp python manage.py migrate

# Collect static files
collectstatic:
	docker-compose exec webapp python manage.py collectstatic --noinput

# Run tests
test:
	docker-compose exec webapp python manage.py test

# Clean up Docker resources
clean:
	docker-compose down -v
	docker system prune -f

# Reset the database and restart
reset: down clean up
	@echo "Database reset complete. Access the application at http://localhost:8000"

.PHONY: help build start stop restart logs logs-webapp logs-db shell makemigrations migrate collectstatic test clean reset
