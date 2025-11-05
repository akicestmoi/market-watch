#!/usr/bin/env python
"""
Standalone script to export the database to a SQL file.

This script exports the entire PostgreSQL database to a SQL dump file
that can be easily transferred and imported on another machine.

Usage:
    python scripts/db_management/export_db.py [--output OUTPUT_PATH]

Or via Docker:
    docker compose -f scripts/docker-compose.yml exec webapp python scripts/db_management/export_db.py [--output OUTPUT_PATH]
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import django
from django.conf import settings

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")


django.setup()


def main():
    parser = argparse.ArgumentParser(
        description="Export the database to a SQL dump file"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file path (default: db_backup_YYYYMMDD_HHMMSS.sql in project root)",
    )
    args = parser.parse_args()

    db_config = settings.DATABASES["default"]
    output_path = args.output

    # Generate default output filename if not provided
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"db_backup_{timestamp}.sql"
        output_path = str(project_root / filename)
    else:
        # Ensure the output directory exists
        output_dir = os.path.dirname(os.path.abspath(output_path))
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

    # Check if pg_dump is available
    try:
        subprocess.run(
            ["pg_dump", "--version"],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(
            "ERROR: pg_dump not found. Please ensure PostgreSQL client tools are installed."
        )
        sys.exit(1)

    # Build pg_dump command (plain SQL format for portability)
    pg_dump_args = [
        "pg_dump",
        "--host",
        db_config["HOST"],
        "--port",
        str(db_config["PORT"]),
        "--username",
        db_config["USER"],
        "--dbname",
        db_config["NAME"],
        "--file",
        output_path,
        "--verbose",
        "--no-owner",
        "--no-acl",
        "--format=plain",  # Plain SQL format for maximum portability
    ]

    # Set PGPASSWORD environment variable
    env = os.environ.copy()
    env["PGPASSWORD"] = db_config["PASSWORD"]

    print(f"Exporting database to: {output_path}")
    print("This may take a few moments...")

    try:
        _ = subprocess.run(
            pg_dump_args,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

        file_size = os.path.getsize(output_path)
        file_size_mb = file_size / (1024 * 1024)

        print("\n✓ Database exported successfully!")
        print(f"File: {output_path}")
        print(f"Size: {file_size_mb:.2f} MB")

        if file_size_mb > 10:
            print(
                f"\nTip: File is large. Consider compressing it with:"
                f"\n  gzip {output_path}"
                f"\nThis will create: {output_path}.gz"
            )

    except subprocess.CalledProcessError as e:
        print(f"ERROR: Error exporting database: {e.stderr}")
        # Clean up partial file if it exists
        if os.path.exists(output_path):
            os.remove(output_path)
            print(f"Removed incomplete file: {output_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
