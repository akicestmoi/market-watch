# Database Management Scripts

This directory contains standalone Python scripts for exporting and importing the database. These scripts are designed to be run via Docker, not as Django management commands.

## Scripts

### `export_db.py` - Export Database to SQL File

Exports the entire PostgreSQL database to a SQL dump file that can be easily transferred.

**Usage via Make:**
```bash
make db-export
```

**Usage via Docker:**
```bash
docker compose -f scripts/docker-compose.yml exec webapp python scripts/db_management/export_db.py
```

**Usage directly (if running locally):**
```bash
python scripts/db_management/export_db.py [--output OUTPUT_PATH]
```

**Options:**
- `--output` or `-o`: Specify the output file path (default: `db_backup_YYYYMMDD_HHMMSS.sql` in project root)

**Examples:**
```bash
# Export with default filename
make db-export

# Export to specific location via Docker
docker compose -f scripts/docker-compose.yml exec webapp python scripts/db_management/export_db.py --output /app/backups/my_backup.sql
```

---

### `import_db.py` - Import Database from SQL File

Imports a database from a SQL dump file. This script will:
1. Validate that the SQL file exists
2. Ask for user confirmation before proceeding
3. Clean the entire database (drop all tables)
4. Run migrations to recreate the schema
5. Import the SQL data
6. Reset sequences to avoid duplicate key violations

**Usage via Make:**
```bash
make db-import SQL_FILE=db_backup_20241028_143022.sql
```

**Usage via Docker:**
```bash
docker compose -f scripts/docker-compose.yml exec webapp python scripts/db_management/import_db.py db_backup.sql
```

**Usage directly (if running locally):**
```bash
python scripts/db_management/import_db.py <sql_file_path> [--no-confirm] [--skip-migrations]
```

**Options:**
- `sql_file`: Path to the SQL dump file to import (required)
- `--no-confirm`: Skip confirmation prompt (useful for scripts)
- `--skip-migrations`: Skip running migrations (use with caution)

**Examples:**
```bash
# Import with confirmation prompt
make db-import SQL_FILE=db_backup_20241028_143022.sql

# Import compressed file
make db-import SQL_FILE=db_backup_20241028_143022.sql.gz

# Import without confirmation (for scripts)
docker compose -f scripts/docker-compose.yml exec webapp python scripts/db_management/import_db.py db_backup.sql --no-confirm
```

**Important Notes:**
- ⚠️ **This will DELETE ALL existing data** in the database
- The SQL file path can be absolute or relative to the project root
- Compressed files (`.sql.gz`) are automatically detected and decompressed
- The script validates the file exists before proceeding
- Sequences are automatically reset after import

---

## Workflow Example

### On Laptop (Export):
```bash
# Export database
make db-export

# This creates: db_backup_20241028_143022.sql
# Optionally compress: gzip db_backup_20241028_143022.sql
# Transfer this file via email/USB to desktop
```

### On Desktop (Import):
```bash
# Place the SQL file in project root or specify path
make db-import SQL_FILE=db_backup_20241028_143022.sql.gz

# Follow the confirmation prompt
# Database will be cleaned and data imported
```

---

## Requirements

- PostgreSQL client tools (`pg_dump` and `psql`) must be installed in the Docker container
- Django project must be properly configured with database settings
- User must have appropriate database permissions

## Troubleshooting

**Error: "pg_dump not found" or "psql not found"**
- The Docker image includes PostgreSQL client tools
- If running locally, install PostgreSQL client tools:
  - On macOS: `brew install postgresql`
  - On Linux: `sudo apt-get install postgresql-client`

**Error: "SQL file not found"**
- Check the file path is correct
- Use absolute path if relative path doesn't work
- Ensure the file exists and is readable
- When using Docker, file paths are relative to `/app` (project root inside container)

**Error: "Permission denied"**
- Ensure database user has proper permissions
- Check database connection settings in `.env`
