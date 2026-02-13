"""
Database module for Stock Analysis Framework
Provides database connection and session management
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Create declarative base for ORM models
Base = declarative_base()

# Database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    logger.warning("DATABASE_URL not set in environment. Using default.")
    # Construct from individual variables
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', '')
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    database = os.getenv('POSTGRES_DB', 'stock_analysis')
    DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{database}"


def get_engine(echo=False):
    """
    Create and return SQLAlchemy engine with connection pooling

    Args:
        echo (bool): If True, log all SQL statements

    Returns:
        Engine: SQLAlchemy engine instance
    """
    return create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,  # Recycle connections after 1 hour
        echo=echo
    )


# Create global engine
engine = get_engine()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db_session():
    """
    Context manager for database sessions
    Automatically handles commit/rollback and session cleanup

    Usage:
        with get_db_session() as session:
            session.query(Stock).filter_by(ticker='AAPL').first()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()


def test_connection():
    """
    Test database connection
    Returns True if successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1
            logger.success("Database connection successful!")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


__all__ = [
    'Base',
    'engine',
    'get_engine',
    'SessionLocal',
    'get_db_session',
    'test_connection'
]
