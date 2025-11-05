FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Make entrypoint script executable and fix line endings (CRLF to LF)
RUN sed -i 's/\r$//' /app/scripts/docker/entrypoint.sh && \
    chmod +x /app/scripts/docker/entrypoint.sh

# Create wrapper script that fixes line endings at runtime (cross-platform compatibility)
# This handles both Windows (CRLF) and Mac/Linux (LF) line endings
RUN echo '#!/bin/bash' > /usr/local/bin/entrypoint-wrapper.sh && \
    echo 'set -e' >> /usr/local/bin/entrypoint-wrapper.sh && \
    echo '# Convert CRLF to LF if needed (works on both Windows and Mac/Linux)' >> /usr/local/bin/entrypoint-wrapper.sh && \
    echo 'sed "s/\r$//" /app/scripts/docker/entrypoint.sh > /tmp/entrypoint.sh && chmod +x /tmp/entrypoint.sh' >> /usr/local/bin/entrypoint-wrapper.sh && \
    echo 'exec /tmp/entrypoint.sh "$@"' >> /usr/local/bin/entrypoint-wrapper.sh && \
    chmod +x /usr/local/bin/entrypoint-wrapper.sh

# Create a non-root user
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Set entrypoint to wrapper (enabling launch on Windows or Mac/Linux)
ENTRYPOINT ["/usr/local/bin/entrypoint-wrapper.sh"]

# Default command
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
