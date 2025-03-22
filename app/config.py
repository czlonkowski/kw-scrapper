"""
Configuration module for the EKW Scraper.
"""
import os
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseModel):
    """Application settings loaded from environment variables."""
    bright_data_username: str = os.getenv("BRIGHT_DATA_USERNAME", "")
    bright_data_password: str = os.getenv("BRIGHT_DATA_PASSWORD", "")
    bright_data_host: str = os.getenv("BRIGHT_DATA_HOST", "")
    bright_data_zone: str = os.getenv("BRIGHT_DATA_ZONE", "")
    bright_data_sb_auth: str = os.getenv("BRIGHT_DATA_SB_AUTH", "")
    bright_data_proxy: str = os.getenv("BRIGHT_DATA_PROXY_1", "")
    max_concurrent: int = int(os.getenv("MAX_CONCURRENT", "3"))
    ekw_portal_url: str = "https://przegladarka-ekw.ms.gov.pl/eukw_prz/KsiegiWieczyste/wyszukiwanieKW?komunikaty=true&kontakt=true&okienkoSerwisowe=false"

# Create and export settings instance
settings = Settings()
