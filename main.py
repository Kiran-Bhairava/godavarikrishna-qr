from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import time

# Import routes with aliases to avoid conflicts
from routes.auth import router as auth_router
from routes.public import router as public_router
from routes.qr import router as qr_router
from routes.social import router as social_router
from routes.hierarchy import router as hierarchy_router
from routes.analytics import router as analytics_router

from database import close_db_connections, check_db_connection
from config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    logger.info(f"Starting GK QR Manager API - Environment: {settings.ENVIRONMENT}")
    
    if await check_db_connection():
        logger.info("✅ Database connection successful")
    else:
        logger.error("❌ Database connection failed")
    
    yield
    
    logger.info("Shutting down GK QR Manager API")
    await close_db_connections()
    logger.info("✅ All connections closed gracefully")


# Create FastAPI app

app = FastAPI(
    title="GK QR Code Manager",
    description="QR code management system with hierarchical analytics for GK Co-operative Society",
    version="3.0.0",
    lifespan=lifespan,
    redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
)

# Custom handler for validation errors (must be after app is defined)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Extract the first error for a concise message
    first_error = exc.errors()[0] if exc.errors() else None
    if first_error:
        loc = ' -> '.join(str(l) for l in first_error.get('loc', []))
        msg = first_error.get('msg', 'Invalid input')
        detail = f"Validation error at {loc}: {msg}"
    else:
        detail = "Invalid request. Please check your input."
    return JSONResponse(
        status_code=422,
        content={
            "detail": detail
        }
    )

# Mount static files
app.mount("/static", StaticFiles(directory="templates"), name="static")


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add response time header to all requests"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
    
    if process_time > 1.0:
        logger.warning(f"Slow request: {request.method} {request.url.path} took {process_time:.2f}s")
    
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions"""
    logger.error(f"Unhandled exception on {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Something went wrong. Please try again later.",
            "path": str(request.url.path)
        }
    )


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time"],
)

# Include routers
app.include_router(auth_router, tags=["Authentication"])
app.include_router(public_router, tags=["Public"])
app.include_router(qr_router, tags=["QR Codes"])
app.include_router(social_router, tags=["Social Links"])
app.include_router(hierarchy_router, tags=["Hierarchy Management"])
app.include_router(analytics_router, tags=["Analytics"])


# Serve static HTML files
@app.get("/")
async def root():
    return FileResponse("templates/index.html")


@app.get("/home")
async def dashboard():
    return FileResponse("templates/dashboard.html")


@app.get("/analytics-page")
async def analytics_page():
    return FileResponse("templates/analytics.html")

@app.get("/hierarchy-analytics")
async def hierarchy_analytics():
    return FileResponse("templates/hierarchy-dashboard.html")

@app.get("/hierarchy")
async def hierarchy_page():
    """Serve the hierarchy management page"""
    return FileResponse("templates/hierarchy.html")


@app.get("/social-analytics")
async def social_analytics():
    return FileResponse("templates/social-analytics.html")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    db_healthy = await check_db_connection()
    
    return {
        "status": "healthy" if db_healthy else "degraded",
        "version": "3.0.0",
        "environment": settings.ENVIRONMENT,
        "database": "connected" if db_healthy else "disconnected"
    }


# Metrics endpoint
@app.get("/metrics")
async def metrics():
    """Basic metrics endpoint"""
    return {
        "app": "gk_qr_manager",
        "version": "3.0.0",
        "environment": settings.ENVIRONMENT,
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
        workers=4 if settings.ENVIRONMENT == "production" else 1,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
        use_colors=True,
    )