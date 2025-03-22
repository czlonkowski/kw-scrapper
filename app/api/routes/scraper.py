"""
API routes for EKW scraper.
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query

from app.models.request import KWRequest
from app.models.response import ScraperResponse, ErrorResponse
from app.core.scraper import scrape_ekw

router = APIRouter(prefix="/api/scraper", tags=["scraper"])


@router.post("/ekw", response_model=ScraperResponse)
async def scrape_ekw_endpoint(
    request: KWRequest, 
    clean_html: bool = Query(True, description="Whether to clean HTML from the response data"),
    debug: bool = Query(False, description="Enable debug mode with screenshots (not recommended for production)")
) -> ScraperResponse:
    """
    Scrape EKW portal for the given KW number.
    
    Args:
        request: KW number details
        clean_html: Whether to clean HTML from the response data
        debug: Enable debug mode with screenshots (not recommended for production)
        
    Returns:
        ScraperResponse: Scraped data or error information
    """
    try:
        result = await scrape_ekw(request, clean_html=clean_html, save_screenshots=debug)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during scraping: {str(e)}"
        )


@router.get("/health", response_model=Dict[str, Any])
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.
    
    Returns:
        Dict[str, Any]: Health status
    """
    return {"status": "ok", "service": "ekw-scraper"}
