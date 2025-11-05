#!/usr/bin/env python
"""
Standalone script to import a database from a SQL dump file.

This script will:
1. Validate that the SQL file exists
2. Ask for user confirmation before proceeding
3. Clean the entire database (drop all tables)
4. Run migrations to recreate the schema
5. Import the SQL data
6. Reset sequences to avoid duplicate key violations

Usage:
    python scripts/db_management/import_db.py <sql_file_path> [--no-confirm] [--skip-migrations]

Or via Docker:
    docker compose -f scripts/docker-compose.yml exec webapp python scripts/db_management/import_db.py <sql_file_path> [--no-confirm] [--skip-migrations]
"""

import argparse
import gzip
import os
import subprocess
import sys
from pathlib import Path

import django
from django.conf import settings
from django.core.management import call_command
from django.db import connection

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")


django.setup()


def drop_all_tables():
    """Drop all tables in the database."""
    with connection.cursor() as cursor:
        # Disable foreign key checks temporarily
        cursor.execute("SET session_replication_role = 'replica';")

        # Get all table names (including django_migrations)
        cursor.execute(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename NOT LIKE 'pg_%';
            """
        )
        tables = [row[0] for row in cursor.fetchall()]

        # Drop all tables (including django_migrations for fresh start)
        if tables:
            for table in tables:
                cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE;')
                print(f"  Dropped table: {table}")

        # Re-enable foreign key checks
        cursor.execute("SET session_replication_role = 'origin';")


def import_sql_file(sql_path, db_config):
    """Import SQL file using psql."""
    # Build psql command
    psql_args = [
        "psql",
        "--host",
        db_config["HOST"],
        "--port",
        str(db_config["PORT"]),
        "--username",
        db_config["USER"],
        "--dbname",
        db_config["NAME"],
        "--quiet",
    ]

    # Set PGPASSWORD environment variable
    env = os.environ.copy()
    env["PGPASSWORD"] = db_config["PASSWORD"]

    # Check if file is compressed
    if str(sql_path).endswith(".gz"):
        print("  Detected compressed file, decompressing...")
        with gzip.open(sql_path, "rt") as f:
            # Read and execute SQL
            sql_content = f.read()
            result = subprocess.run(
                psql_args,
                input=sql_content,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
    else:
        psql_args.append("--file")
        psql_args.append(str(sql_path))
        result = subprocess.run(
            psql_args,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

    if result.returncode != 0:
        raise Exception(f"psql error: {result.stderr}")


def reset_sequences():
    """Reset all PostgreSQL sequences to avoid duplicate key violations."""
    with connection.cursor() as cursor:
        # Get all tables with sequences
        cursor.execute(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename NOT LIKE 'pg_%'
            AND tablename != 'django_migrations';
            """
        )
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            try:
                # Get the current maximum ID from the table
                cursor.execute(f'SELECT MAX(id) FROM "{table}";')
                max_id = cursor.fetchone()[0]

                if max_id is None:
                    # No data, set sequence to start at 1
                    cursor.execute(f'ALTER SEQUENCE "{table}_id_seq" RESTART WITH 1;')
                    print(f"  Reset {table} sequence to start from: 1")
                else:
                    # Set sequence to start from max_id + 1
                    next_id = max_id + 1
                    cursor.execute(
                        f'ALTER SEQUENCE "{table}_id_seq" RESTART WITH {next_id};'
                    )
                    print(f"  Reset {table} sequence to start from: {next_id}")
            except Exception:
                # Some tables might not have an id column or sequence
                # This is fine, just skip them
                continue


def main():
    parser = argparse.ArgumentParser(
        description="Import a database from a SQL dump file"
    )
    parser.add_argument(
        "sql_file",
        type=str,
        help="Path to the SQL dump file to import",
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Skip confirmation prompt (useful for scripts)",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Skip running migrations (use with caution)",
    )
    args = parser.parse_args()

    sql_file = args.sql_file
    no_confirm = args.no_confirm
    skip_migrations = args.skip_migrations

    # Validate SQL file exists
    sql_path = Path(sql_file)
    if not sql_path.is_absolute():
        # Try relative to project root
        sql_path = project_root / sql_file

    if not sql_path.exists():
        print(f"ERROR: SQL file not found: {sql_path}")
        print("Please provide the correct path to your SQL dump file.")
        sys.exit(1)

    if not sql_path.is_file():
        print(f"ERROR: Path is not a file: {sql_path}")
        sys.exit(1)

    # Check file size
    file_size = sql_path.stat().st_size
    file_size_mb = file_size / (1024 * 1024)

    print(
        f"\n{'='*60}\n"
        f"IMPORT DATABASE\n"
        f"{'='*60}\n"
        f"File: {sql_path}\n"
        f"Size: {file_size_mb:.2f} MB\n"
        f"\nWARNING: This will:\n"
        f"  1. DELETE ALL existing data in the database\n"
        f"  2. Drop all tables\n"
        f"  3. Run migrations to recreate schema\n"
        f"  4. Import data from the SQL file\n"
        f"  5. Reset sequences\n"
        f"\nDatabase: {settings.DATABASES['default']['NAME']}\n"
        f"{'='*60}\n"
    )

    # Ask for confirmation
    if not no_confirm:
        confirm = input("\nAre you sure you want to proceed? (y/n): ")
        if confirm != "y":
            print("Import cancelled.")
            sys.exit(0)

    db_config = settings.DATABASES["default"]

    # Step 1: Check if psql is available
    try:
        subprocess.run(
            ["psql", "--version"],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(
            "ERROR: psql not found. Please ensure PostgreSQL client tools are installed."
        )
        sys.exit(1)

    # Step 2: Clean the database (drop all tables)
    print("\nStep 1: Cleaning database...")
    try:
        drop_all_tables()
        print("✓ Database cleaned successfully")
    except Exception as e:
        print(f"ERROR: Error cleaning database: {str(e)}")
        sys.exit(1)

    # Step 3: Import SQL file first (contains schema and data)
    print("\nStep 2: Importing SQL data...")
    try:
        import_sql_file(sql_path, db_config)
        print("✓ Data imported successfully")
    except Exception as e:
        print(f"ERROR: Error importing SQL file: {str(e)}")
        sys.exit(1)

    # Step 4: Run migrations (will detect any new migrations since dump was created)
    if not skip_migrations:
        print("\nStep 3: Checking for new migrations...")
        try:
            # Use --fake-initial to mark existing migrations as applied
            # This works because the SQL dump already contains the schema
            call_command("migrate", "--fake-initial", verbosity=1)
            # Then run any new migrations that might exist
            call_command("migrate", verbosity=1)
            print("✓ Migrations completed successfully")
        except Exception as e:
            print(f"Warning: Migration check failed: {str(e)}")
            print("Database should still be functional if SQL dump was complete.")
    else:
        print("Step 3: Skipping migrations (--skip-migrations)")

    # Step 5: Reset sequences
    print("\nStep 4: Resetting sequences...")
    try:
        reset_sequences()
        print("✓ Sequences reset successfully")
    except Exception as e:
        print(f"Warning: Could not reset sequences: {str(e)}")
        print("You may need to run reset_sequences manually.")

    print(f"\n{'='*60}\n" f"Database import completed successfully!\n" f"{'='*60}\n")


if __name__ == "__main__":
    main()
