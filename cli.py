"""
CLI tool for testing EKW scraper functionality.
"""
import asyncio
import json
import argparse
import logging
from typing import Dict, Any

from app.models.request import KWRequest
from app.core.scraper import scrape_ekw

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_scraper(kod_wydzialu: str, numer_ksiegi_wieczystej: str, cyfra_kontrolna: str) -> Dict[str, Any]:
    """
    Run the scraper with the given KW number.
    
    Args:
        kod_wydzialu: Code of the department
        numer_ksiegi_wieczystej: Number of the land register
        cyfra_kontrolna: Check digit
        
    Returns:
        Dict[str, Any]: Scraped data or error information
    """
    request = KWRequest(
        kod_wydzialu=kod_wydzialu,
        numer_ksiegi_wieczystej=numer_ksiegi_wieczystej,
        cyfra_kontrolna=cyfra_kontrolna
    )
    
    result = await scrape_ekw(request)
    return result.model_dump()


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(description="EKW Scraper CLI")
    parser.add_argument("--kod", required=True, help="Kod wydziału (e.g., WA1M)")
    parser.add_argument("--numer", required=True, help="Numer księgi wieczystej (e.g., 00533284)")
    parser.add_argument("--cyfra", required=True, help="Cyfra kontrolna (e.g., 3)")
    parser.add_argument("--output", help="Output file path (optional)")
    
    args = parser.parse_args()
    
    logger.info(f"Starting scraper for KW: {args.kod}/{args.numer}/{args.cyfra}")
    
    result = asyncio.run(run_scraper(args.kod, args.numer, args.cyfra))
    
    # Pretty print result
    result_json = json.dumps(result, indent=2, ensure_ascii=False)
    print(result_json)
    
    # Save to file if output path is provided
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result_json)
        logger.info(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
