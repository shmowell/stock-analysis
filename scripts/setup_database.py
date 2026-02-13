"""
Database Setup Script for Stock Analysis Framework
Creates PostgreSQL database and initializes all tables

Usage:
    python scripts/setup_database.py

Environment Variables Required:
    - POSTGRES_USER
    - POSTGRES_PASSWORD
    - POSTGRES_HOST
    - POSTGRES_PORT
    - POSTGRES_DB
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, inspect, text
from loguru import logger

# Load environment variables
load_dotenv()


def get_db_credentials():
    """Extract database credentials from environment"""
    return {
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD'),
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'database': os.getenv('POSTGRES_DB', 'stock_analysis')
    }


def create_database_if_not_exists(creds):
    """
    Create the PostgreSQL database if it doesn't exist
    Connects to 'postgres' database first to check/create target database
    """
    logger.info(f"Checking if database '{creds['database']}' exists...")

    # Connect to PostgreSQL server (postgres database)
    try:
        conn = psycopg2.connect(
            user=creds['user'],
            password=creds['password'],
            host=creds['host'],
            port=creds['port'],
            database='postgres'  # Connect to default postgres database
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (creds['database'],)
        )
        exists = cursor.fetchone()

        if not exists:
            logger.info(f"Database '{creds['database']}' not found. Creating...")
            cursor.execute(f"CREATE DATABASE {creds['database']}")
            logger.success(f"Database '{creds['database']}' created successfully!")
        else:
            logger.info(f"Database '{creds['database']}' already exists.")

        cursor.close()
        conn.close()
        return True

    except psycopg2.Error as e:
        logger.error(f"Error creating database: {e}")
        return False


def get_database_url(creds):
    """Construct SQLAlchemy database URL"""
    return f"postgresql://{creds['user']}:{creds['password']}@{creds['host']}:{creds['port']}/{creds['database']}"


def create_tables(engine):
    """
    Create all tables using SQLAlchemy models
    Import models module which will define all tables
    """
    logger.info("Creating database tables...")

    try:
        # Import database models (will create when ready)
        # from src.database.models import Base
        # Base.metadata.create_all(engine)

        # For now, we'll use raw SQL to create tables
        # This will be replaced with SQLAlchemy models in Phase 1
        with engine.connect() as conn:
            # Execute table creation SQL
            from pathlib import Path
            sql_file = Path(__file__).parent / 'init_db.sql'

            if sql_file.exists():
                logger.info(f"Executing SQL from {sql_file}")
                with open(sql_file, 'r') as f:
                    sql_script = f.read()
                    conn.execute(text(sql_script))
                    conn.commit()
                logger.success("Tables created successfully from SQL script!")
            else:
                logger.warning(f"SQL file not found: {sql_file}")
                logger.info("Skipping table creation. Run this again after creating init_db.sql")

        return True

    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return False


def verify_tables(engine):
    """Verify that tables were created successfully"""
    logger.info("Verifying table creation...")

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    expected_tables = [
        'stocks',
        'price_data',
        'fundamental_data',
        'technical_indicators',
        'sentiment_data',
        'market_sentiment',
        'stock_scores',
        'override_decisions',
        'quarterly_reviews',
        'api_call_log',
        'calculation_log'
    ]

    logger.info(f"Found {len(tables)} tables in database")

    missing_tables = set(expected_tables) - set(tables)
    if missing_tables:
        logger.warning(f"Missing tables: {missing_tables}")
        return False
    else:
        logger.success("All expected tables created successfully!")
        logger.info(f"Tables: {', '.join(sorted(tables))}")
        return True


def main():
    """Main setup function"""
    logger.info("=" * 60)
    logger.info("Stock Analysis Framework - Database Setup")
    logger.info("=" * 60)

    # Get credentials
    creds = get_db_credentials()

    if not creds['password']:
        logger.error("POSTGRES_PASSWORD not set in .env file")
        logger.info("Please update your .env file with PostgreSQL credentials")
        return False

    logger.info(f"Connecting to PostgreSQL at {creds['host']}:{creds['port']}")

    # Step 1: Create database if needed
    if not create_database_if_not_exists(creds):
        logger.error("Failed to create database. Exiting.")
        return False

    # Step 2: Create engine
    database_url = get_database_url(creds)
    logger.info(f"Creating SQLAlchemy engine for {creds['database']}")

    try:
        engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            echo=False  # Set to True for SQL debugging
        )

        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            logger.success(f"Connected to PostgreSQL: {version[:50]}...")

    except Exception as e:
        logger.error(f"Failed to create engine: {e}")
        return False

    # Step 3: Create tables
    if not create_tables(engine):
        logger.warning("Table creation had issues. Check logs above.")
        # Don't return False, continue to verify

    # Step 4: Verify tables
    verify_tables(engine)

    logger.info("=" * 60)
    logger.success("Database setup complete!")
    logger.info("=" * 60)
    logger.info("\nNext steps:")
    logger.info("1. Review database schema: docs/database_schema.md")
    logger.info("2. Test connection: python -c 'from src.database import get_engine; print(get_engine())'")
    logger.info("3. Begin Phase 1 data collection")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
