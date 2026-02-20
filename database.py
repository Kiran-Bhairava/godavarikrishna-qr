import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator
import logging
from dotenv import load_dotenv
load_dotenv()

from config import settings

# Configure logging
logger = logging.getLogger(__name__)

# PostgreSQL connection string from config
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
# OPTIMIZED: Create async engine with proper pool configuration
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.ENABLE_QUERY_LOGGING,  # Only log queries in development
    future=True,
    pool_pre_ping=settings.DB_POOL_PRE_PING,  # Test connections before use
    pool_size=settings.DB_POOL_SIZE,  # Number of connections in pool
    max_overflow=settings.DB_MAX_OVERFLOW,  # Additional connections when needed
    pool_recycle=settings.DB_POOL_RECYCLE,  # Recycle stale connections
    pool_timeout=30,  # Wait 30s for available connection
    connect_args={
        "server_settings": {
            "application_name": "social_media",  # Identify connections in PostgreSQL
        }
    }
)

# OPTIMIZED: Session factory with proper configuration
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit
    autoflush=False,  # Manual control over flushing
    autocommit=False,
)

# Base class for models
Base = declarative_base()

# OPTIMIZED: Dependency for FastAPI routes with better error handling
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Database session dependency with proper transaction management.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error: {str(e)}", exc_info=True)
            raise
        finally:
            await session.close()


# OPTIMIZED: Connection health check
async def check_db_connection():
    """
    Check if database connection is healthy.
    Useful for health check endpoints.
    """
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False


# OPTIMIZED: Graceful shutdown
async def close_db_connections():
    """
    Close all database connections gracefully.
    Call this on application shutdown.
    """
    await engine.dispose()
    logger.info("Database connections closed")