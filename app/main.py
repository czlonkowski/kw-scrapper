"""
Main FastAPI application for EKW Scraper.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

from app.api.routes.scraper import router as scraper_router
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup: Install Playwright browsers if needed
    logger.info("Starting up EKW Scraper API")
    try:
        playwright = await async_playwright().start()
        await playwright.stop()
        logger.info("Playwright initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing Playwright: {str(e)}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down EKW Scraper API")


# Create FastAPI application
app = FastAPI(
    title="EKW Scraper API",
    description="API for scraping EKW (Electronic Land and Mortgage Register) portal",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for all unhandled exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error", "details": str(exc)},
    )


# Include routers
app.include_router(scraper_router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "EKW Scraper API",
        "version": "1.0.0",
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
