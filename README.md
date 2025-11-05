# Market Watch

A Django-based market monitoring application with comprehensive API documentation, Docker support, and development tools.

## Quick Start

### For Local Development

1. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Unix/MacOS
   source venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   npm install  # For linters
   ```

3. **Set up environment variables**:
   Create a `.env` file in the project root:
   ```env
   SECRET_KEY
   POSTGRES_DB
   POSTGRES_USER
   POSTGRES_PASSWORD
   DB_HOST
   DB_PORT
   FRED_API_KEY
   CELERY_BROKER_URL
   CELERY_RESULT_BACKEND
   ```

4. **Set up database and start server**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py runserver
   ```

5. **Access the application**:
   - Main App: http://127.0.0.1:8000/
   - API Documentation: http://127.0.0.1:8000/api/docs/
   - Admin Panel: http://127.0.0.1:8000/admin/

### For Docker Development

1. **Start with Docker**:
   ```bash
   make start
   ```

2. **Access the application**:
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/api/docs/
   - Admin Panel: http://localhost:8000/admin/ (admin/admin123)

3. **Port conflicts:**
   ```bash
   make stop
   ```

4. **View logs:**
   ```bash
   make logs-webapp  # Webapp container logs
   ```

5. Docker Commands
   Use the Makefile for convenient commands:

   ```bash
   make help            # Show all available commands
   make install         # Install dependencies
	make lint            # Lint the code
	make flake8          # Run Flake8
	make pyright         # Run Pyright
   make build           # Build the Docker image
   make start           # Start the application
   make stop            # Stop all containers
   make restart         # Restart all containers
   make logs            # Show logs from all containers
   make logs-webapp     # Show logs from webapp container
   make shell           # Open a shell in the webapp container
   make makemigrations  # Prepare database migrations
   make migrate         # Run database migrations
   make collectstatic   # Collect static files
   make celery-beat     # Start periodic tasks
   make celery-worker   # Execute worker
   make test            # Run tests
   make clean           # Clean up Docker resources
   make db-export       # Export database to SQL file
	make db-import       # Import database from SQL file (requires SQL_FILE=path)
   ```

## API Documentation

The application includes comprehensive OpenAPI documentation:

- **Swagger UI**: http://localhost:8000/api/docs/
- **Schema**: http://localhost:8000/api/schema/


## Celery Task Scheduling

The application includes automated market data ingestion using Celery and Redis:
Django Web App ==> Celery Beat (Scheduler) ==> Redis (Broker) ==> Worker Process


### **Scheduled Tasks**
Market data is automatically ingested **3 times daily (Europe/Paris Time)**:
- **8:00 AM** - Morning market data
- **2:00 PM** - Afternoon market data
- **8:00 PM** - Evening market data
