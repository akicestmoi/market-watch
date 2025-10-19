#!/bin/bash

set -e

# Function to wait for database
wait_for_db() {
    echo "Waiting for database..."
    while ! nc -z $DB_HOST $DB_PORT; do
        sleep 1
    done
    echo "Database is ready!"
}

# Set default values if not provided
export DB_HOST=${DB_HOST}
export DB_PORT=${DB_PORT}

# Wait for database to be ready
wait_for_db

# Prepare database migrations
echo "Preparing database migrations..."
python manage.py makemigrations

# Run database migrations
echo "Running database migrations..."
python manage.py migrate

# Collect static files (if needed)
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Execute the main command
echo "Starting server..."
exec "$@"
