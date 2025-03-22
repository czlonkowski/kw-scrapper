"""
Response models for EKW Scraper API.
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class SectionData(BaseModel):
    """Base model for section data."""
    content: Dict[str, Any] = Field(default_factory=dict)
    raw_html: Optional[str] = None


class DzialIO(SectionData):
    """Data for Dział I-O (Section I-O)."""
    pass


class DzialISp(SectionData):
    """Data for Dział I-Sp (Section I-Sp)."""
    pass


class DzialII(SectionData):
    """Data for Dział II (Section II)."""
    pass


class DzialIII(SectionData):
    """Data for Dział III (Section III)."""
    pass


class DzialIV(SectionData):
    """Data for Dział IV (Section IV)."""
    pass


class ScraperResponse(BaseModel):
    """
    Response model for EKW scraping results.
    
    Attributes:
        success: Whether the scraping was successful
        error: Error message if scraping failed
        kw_number: Full KW number
        dzial_io: Data from Dział I-O section
        dzial_isp: Data from Dział I-Sp section
        dzial_ii: Data from Dział II section
        dzial_iii: Data from Dział III section
        dzial_iv: Data from Dział IV section
    """
    success: bool = True
    error: Optional[str] = None
    kw_number: Optional[str] = None
    dzial_io: Optional[DzialIO] = None
    dzial_isp: Optional[DzialISp] = None
    dzial_ii: Optional[DzialII] = None
    dzial_iii: Optional[DzialIII] = None
    dzial_iv: Optional[DzialIV] = None


class ErrorResponse(BaseModel):
    """
    Error response model.
    
    Attributes:
        success: Always False for error responses
        error: Error message
        details: Additional error details
    """
    success: bool = False
    error: str
    details: Optional[Dict[str, Any]] = None
