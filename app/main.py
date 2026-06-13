"""
FastAPI Application Entry Point
Main application initialization and configuration
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models.database import Base
from app.api.routes import router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


def init_db():
    """Initialize database tables"""
    try:
        engine = create_engine(settings.DATABASE_URL)
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for app lifecycle
    Startup: Initialize database
    Shutdown: Cleanup (if needed)
    """
    # Startup
    logger.info("Starting up FastAPI application")
    init_db()
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI application")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application
    
    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="Transaction Processing Pipeline",
        description="AI-Powered Transaction Processing Pipeline with LLM Classification",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routes
    app.include_router(router)
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "ok", "version": "1.0.0"}
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "message": "Transaction Processing Pipeline API",
            "docs": "/docs",
            "status": "ready",
        }
    
    logger.info("FastAPI application created successfully")
    return app


# Create app instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
