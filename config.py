
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Database Pool Settings (OPTIMIZED)
    DB_POOL_SIZE: int = 20  # Number of connections to maintain
    DB_MAX_OVERFLOW: int = 10  # Additional connections when pool is full
    DB_POOL_RECYCLE: int = 3600  # Recycle connections after 1 hour
    DB_POOL_PRE_PING: bool = True  # Test connections before using
    
    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    
    # Server
    BASE_URL: str = "https://qr-code-2-0-22ky.onrender.com"
    ENVIRONMENT: str = "production"  # development, staging, production
    
    # Logging
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    
    # # Redis Cache (Optional - add when implementing caching)
    # REDIS_URL: Optional[str] = None  # "redis://localhost:6379"
    # CACHE_TTL: int = 300  # 5 minutes default cache
    
    # # Rate Limiting
    # RATE_LIMIT_ENABLED: bool = True
    # RATE_LIMIT_PER_MINUTE: int = 60
    
    # Performance
    ENABLE_QUERY_LOGGING: bool = False  # Set to False in production
    
    # Background Tasks
    ENABLE_BACKGROUND_TASKS: bool = True
    LOCATION_LOOKUP_ASYNC: bool = True  # Lookup location in background
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()