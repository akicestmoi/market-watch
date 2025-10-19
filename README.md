# Market Watch 📊

A Django-based market monitoring application with comprehensive API documentation, Docker support, and development tools.

## 🚀 Quick Start

### Option 1: Local Development

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
   SECRET_KEY=your-secret-key-here
   POSTGRES_DB=market_watch
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your-password
   DB_HOST=localhost
   DB_PORT=5432
   FRED_API_KEY=your-api-key
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

### Option 2: Docker Development

1. **Start with Docker**:
   ```bash
   make start
   ```
   or
   ```bash
   docker-compose up --build
   ```

2. **Access the application**:
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/api/docs/
   - Admin Panel: http://localhost:8000/admin/ (admin/admin123)

## 🐳 Docker Commands

Use the Makefile for convenient commands:

```bash
make help          # Show all available commands
make build         # Build the Docker image
make start         # Start the application
make stop          # Stop all containers
make restart       # Restart all containers
make logs          # Show logs from all containers
make logs-webapp   # Show logs from webapp container
make logs-db       # Show logs from database container
make shell         # Open a shell in the webapp container
make makemigrations # Prepare database migrations
make migrate       # Run database migrations
make collectstatic # Collect static files
make test          # Run tests
make clean         # Clean up Docker resources
make reset         # Reset the database and restart
```

## 📊 API Documentation

The application includes comprehensive OpenAPI documentation:

- **Swagger UI**: http://localhost:8000/api/docs/
- **Schema**: http://localhost:8000/api/schema/

### API Features

#### Market Data Management
- **Ingest Market Prices**: Scrap and ingest market prices from various sources (Yahoo Finance, Global Rates, Bloomberg)
- **Ingest Asset-Specific Data**: Scrap historical data for specific assets over target periods
- **Get Market Price Data**: Retrieve market price data with support for single asset or date-based queries
- **Update Market Price Data**: Update existing price data with audit logging

#### Price Analysis & Calculations
- **Calculate Price Changes**: Calculate percentage and absolute price changes between two dates for all assets
- **Get Yield Curves**: Retrieve bond yield data across different maturities for specific dates and locations
- **Get Historical Prices**: Access historical price data for specific assets within date ranges

#### Asset & Data Management
- **Get Asset Names**: Retrieve lists of all assets with filtering by asset class, type, location, or source
- **Get Price Update Logs**: Track data changes and corrections with filtering by date and/or asset
- **Database Operations**: Full CRUD operations with comprehensive audit logging

#### Documentation Features
- **Request/Response Examples**: All endpoints include detailed examples
- **Parameter Documentation**: Comprehensive parameter descriptions and validation rules
- **Error Handling**: Detailed error responses with examples
- **Interactive Testing**: Test endpoints directly from the Swagger UI

## 📂 Project Structure

```
market-watch/
├── core/                    # Django core settings
├── data_visualization/      # Data visualization app
├── economic_overview/       # Economic data app
├── market_overview/         # Market data app
├── shared/                  # Shared utilities
├── .vscode/                 # VS Code configuration
├── Dockerfile              # Docker container definition
├── docker-compose.yml      # Docker services configuration
├── Makefile                # Convenient Docker commands
├── entrypoint.sh           # Docker startup script
└── README.md               # This file
```

## 🚨 Troubleshooting

### Local Development

**Port already in use:**
```bash
# Kill processes using port 8000
lsof -ti:8000 | xargs kill -9
```

**Database connection issues:**
```bash
# Check if PostgreSQL is running
brew services start postgresql  # macOS
sudo service postgresql start   # Linux
```

**Linter not working:**
```bash
# Reload VS Code window
Ctrl+Shift+P → "Reload Window"
```

### Docker Development

**Port conflicts:**
```bash
make stop
# or
docker-compose down
```

**Database issues:**
```bash
make reset  # Reset database and restart
```

**View logs:**
```bash
make logs-webapp  # Webapp container logs
make logs-db      # Database logs
```
