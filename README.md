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

The application includes automated data ingestion and maintenance tasks using Celery and Redis:
Django Web App ==> Celery Beat (Scheduler) ==> Redis (Broker) ==> Worker Process

### Scheduled Tasks Overview

All scheduled tasks run in **Europe/Paris timezone**. Tasks are organized into two categories:

#### **Data Ingestion Tasks** (Daily/Regular - Weekdays Only)

These tasks fetch and ingest data from external sources:

1. **Market Data Ingestion** - Runs **3 times daily** (8:00 AM, 2:00 PM, 8:00 PM)
   - Ingests asset prices: stocks, FX, crypto, commodities, government bond rates
   - Task: `market_overview.tasks.scheduled_market_data_ingestion`

2. **STIR Futures Prices Ingestion** - Runs **2 times daily** (8:00 AM, 8:40 PM)
   - Ingests Short-Term Interest Rate futures prices (FedFunds, ESTR, TONA)
   - Task: `central_banks_overview.tasks.scheduled_stir_prices_ingestion`

3. **Economic Data and Schedule Update** - Runs **daily** (8:00 AM)
   - Ingests economic indicators and updates publication schedules
   - Task: `economic_overview.tasks.scheduled_economic_data_and_schedule_update`

4. **Central Bank Meetings and STIR Futures Cleanup** - Runs **daily** (8:00 AM)
   - Updates central bank meeting dates
   - Cleans up old STIR futures prices (keeps last 7 days)
   - Task: `central_banks_overview.tasks.scheduled_update_cb_meetings_and_stir_futures_prices_cleanup`

#### **Maintenance Tasks** (Monthly - 1st of each month at 8:00 AM)

These tasks clean up old data and maintain database health:

1. **Price Update Logs Cleanup**
   - Deletes price update logs older than 1 month
   - Task: `market_overview.tasks.scheduled_price_update_logs_cleanup`

2. **STIR Futures Price Update Logs Cleanup**
   - Deletes STIR futures price update logs older than 1 month
   - Task: `central_banks_overview.tasks.scheduled_stir_futures_price_update_logs_cleanup`

3. **Economic Data Update Logs Cleanup**
   - Deletes economic data update logs older than 1 month
   - Task: `economic_overview.tasks.scheduled_economic_data_update_logs_cleanup`

4. **Holidays Ingestion**
   - Ingests holidays for all supported countries (US, FR, DE, JP)
   - Task: `market_overview.tasks.scheduled_holidays_ingestion`

### Task Schedule Summary

| Task | Frequency | Schedule | Time |
|------|-----------|----------|------|
| Market Data Ingestion | 3x daily | Weekdays | 8:00, 14:00, 20:00 |
| STIR Prices Ingestion | 2x daily | Weekdays | 8:00, 20:40 |
| Economic Data Update | Daily | Weekdays | 8:00 |
| CB Meetings & Cleanup | Daily | Weekdays | 8:00 |
| Logs Cleanup (All) | Monthly | 1st of month | 8:00 |
| Holidays Ingestion | Monthly | 1st of month | 8:00 |
