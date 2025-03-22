"""
Request models for EKW Scraper API.
"""
from pydantic import BaseModel, Field


class KWRequest(BaseModel):
    """
    Request model for EKW scraping.
    
    Attributes:
        kod_wydzialu: Code of the department (e.g., WA1M)
        numer_ksiegi_wieczystej: Number of the land register (e.g., 00533284)
        cyfra_kontrolna: Check digit (e.g., 3)
    """
    kod_wydzialu: str = Field(..., description="Code of the department (e.g., WA1M)")
    numer_ksiegi_wieczystej: str = Field(..., description="Number of the land register (e.g., 00533284)")
    cyfra_kontrolna: str = Field(..., description="Check digit (e.g., 3)")
