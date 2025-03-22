"""
Core scraping functionality for EKW portal.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from playwright.async_api import Page

from app.config import settings
from app.utils.browser import (
    initialize_browser,
    close_browser,
    navigate_to_url,
    fill_input,
    click_element,
    wait_for_element,
    get_element_text,
    get_elements_text,
    extract_html_content,
    accept_cookies
)
from app.utils.html_cleaner import clean_scraped_data
from app.models.request import KWRequest
from app.models.response import (
    ScraperResponse,
    DzialIO,
    DzialISp,
    DzialII,
    DzialIII,
    DzialIV
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def scrape_ekw(request: KWRequest, clean_html: bool = True) -> ScraperResponse:
    """
    Main function to scrape EKW portal.
    
    Args:
        request: KWRequest object containing KW number details
        clean_html: Whether to clean HTML from the response data
        
    Returns:
        ScraperResponse: Scraped data or error information
    """
    playwright = None
    browser = None
    
    try:
        # Initialize browser with shorter timeout
        playwright, browser, page = await initialize_browser()
        logger.info("Browser initialized successfully")
        
        # Set default timeout for all operations
        page.set_default_timeout(15000)  # 15 seconds timeout
        
        # Navigate to EKW portal
        await navigate_to_url(page, settings.ekw_portal_url)
        logger.info(f"Navigated to EKW portal: {settings.ekw_portal_url}")
        
        # Accept cookies if present (with shorter timeout)
        try:
            await accept_cookies(page)
            logger.info("Attempted to accept cookies if present")
        except Exception as e:
            logger.warning(f"Cookie acceptance failed, but continuing: {str(e)}")
        
        # Take a screenshot for debugging
        await page.screenshot(path="debug_initial_page.png")
        logger.info("Saved initial page screenshot for debugging")
        
        # Fill in the KW number fields
        await fill_kw_form(page, request)
        logger.info(f"Filled KW form with: {request.kod_wydzialu}/{request.numer_ksiegi_wieczystej}/{request.cyfra_kontrolna}")
        
        # Click search button
        await click_element(page, "#wyszukaj")
        logger.info("Clicked search button")
        
        # Wait for results page with reduced timeout
        try:
            await wait_for_element(page, "#przyciskWydrukZwykly", timeout=15000)
            logger.info("Search results loaded successfully")
            
            # Take a screenshot of the results page
            await page.screenshot(path="debug_results_page.png")
            logger.info("Saved results page screenshot for debugging")
        except Exception as e:
            # Take a screenshot of the error page
            await page.screenshot(path="debug_error_page.png")
            logger.info("Saved error page screenshot for debugging")
            
            # Check if there's an error message
            error_msg = await get_error_message(page)
            if error_msg:
                logger.error(f"Error during search: {error_msg}")
                return ScraperResponse(
                    success=False,
                    error=error_msg,
                    kw_number=f"{request.kod_wydzialu}/{request.numer_ksiegi_wieczystej}/{request.cyfra_kontrolna}"
                )
            else:
                logger.error(f"Timeout waiting for search results: {str(e)}")
                return ScraperResponse(
                    success=False,
                    error="Timeout waiting for search results",
                    kw_number=f"{request.kod_wydzialu}/{request.numer_ksiegi_wieczystej}/{request.cyfra_kontrolna}"
                )
        
        # Click on "Przeglądanie aktualnej treści KW" button
        await click_element(page, "#przyciskWydrukZwykly")
        logger.info("Clicked on 'Przeglądanie aktualnej treści KW' button")
        
        # Process each section
        sections_data = await process_all_sections(page)
        
        # Clean HTML if requested
        if clean_html:
            sections_data = clean_scraped_data(sections_data)
            logger.info("Cleaned HTML from scraped data")
        
        # Create response object
        response = ScraperResponse(
            success=True,
            kw_number=f"{request.kod_wydzialu}/{request.numer_ksiegi_wieczystej}/{request.cyfra_kontrolna}",
            **sections_data
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error during scraping: {str(e)}")
        return ScraperResponse(
            success=False,
            error=f"Error during scraping: {str(e)}",
            kw_number=f"{request.kod_wydzialu}/{request.numer_ksiegi_wieczystej}/{request.cyfra_kontrolna}"
        )
    finally:
        # Close browser
        if browser and playwright:
            await close_browser(playwright, browser)
            logger.info("Browser closed")


async def fill_kw_form(page: Page, request: KWRequest) -> None:
    """
    Fill in the KW number form.
    
    Args:
        page: Playwright page object
        request: KWRequest object containing KW number details
    """
    # Fill in the code field
    await fill_input(page, "#kodWydzialuInput", request.kod_wydzialu)
    
    # Fill in the number field
    await fill_input(page, "#numerKsiegiWieczystej", request.numer_ksiegi_wieczystej)
    
    # Fill in the check digit field
    await fill_input(page, "#cyfraKontrolna", request.cyfra_kontrolna)


async def get_error_message(page: Page) -> Optional[str]:
    """
    Extract error message from the page if present.
    
    Args:
        page: Playwright page object
        
    Returns:
        Optional[str]: Error message if found, None otherwise
    """
    error_selectors = [
        ".error:not(.hide)",
        ".error-message",
        "#errorMessageBox"
    ]
    
    for selector in error_selectors:
        try:
            elements = await page.query_selector_all(selector)
            if elements:
                messages = []
                for element in elements:
                    text = await element.inner_text()
                    if text and text.strip():
                        messages.append(text.strip())
                if messages:
                    return " | ".join(messages)
        except Exception:
            continue
    
    return None


async def process_all_sections(page: Page) -> Dict[str, Any]:
    """
    Process all sections of the KW document.
    
    Args:
        page: Playwright page object
        
    Returns:
        Dict[str, Any]: Dictionary containing data from all sections
    """
    sections = {
        "dzial_io": {"selector": "input[value='Dział I-O']", "parser": parse_dzial_io},
        "dzial_isp": {"selector": "input[value='Dział I-Sp']", "parser": parse_dzial_isp},
        "dzial_ii": {"selector": "input[value='Dział II']", "parser": parse_dzial_ii},
        "dzial_iii": {"selector": "input[value='Dział III']", "parser": parse_dzial_iii},
        "dzial_iv": {"selector": "input[value='Dział IV']", "parser": parse_dzial_iv}
    }
    
    result = {}
    
    for section_name, section_info in sections.items():
        try:
            # Click on section button
            await click_element(page, section_info["selector"])
            logger.info(f"Clicked on {section_name} button")
            
            # Wait for section content to load with shorter timeout
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            # Extract HTML content
            html_content = await extract_html_content(page, "body")
            
            # Parse section data
            section_data = await section_info["parser"](page, html_content)
            result[section_name] = section_data
            
            logger.info(f"Processed {section_name} successfully")
            
        except Exception as e:
            logger.error(f"Error processing {section_name}: {str(e)}")
            # Create empty section data with error
            section_class = globals()[section_name.title().replace("_", "")]
            result[section_name] = section_class(
                content={"title": f"DZIAŁ {section_name.upper().replace('DZIAL_', '').replace('_', '-')}", "error": f"Failed to process section: {str(e)}"},
                raw_html=None
            )
    
    return result


async def parse_dzial_io(page: Page, html_content: str) -> DzialIO:
    """
    Parse data from Dział I-O section.
    
    Args:
        page: Playwright page object
        html_content: HTML content of the section
        
    Returns:
        DzialIO: Parsed data
    """
    content = {}
    
    # Extract table data
    tables = await page.query_selector_all("table.tabela-dane")
    
    if tables:
        # Process first table - general information
        if len(tables) > 0:
            rows = await tables[0].query_selector_all("tr")
            for row in rows:
                cells = await row.query_selector_all("td")
                if len(cells) >= 2:
                    key = await cells[0].inner_text()
                    value = await cells[1].inner_text()
                    content[key.strip()] = value.strip()
        
        # Process second table - location information
        if len(tables) > 1:
            location_data = []
            rows = await tables[1].query_selector_all("tr")
            headers = []
            
            for i, row in enumerate(rows):
                cells = await row.query_selector_all("td")
                
                if i == 0:  # Header row
                    for cell in cells:
                        headers.append(await cell.inner_text())
                else:  # Data rows
                    row_data = {}
                    for j, cell in enumerate(cells):
                        if j < len(headers):
                            row_data[headers[j].strip()] = (await cell.inner_text()).strip()
                    if row_data:
                        location_data.append(row_data)
            
            content["location_data"] = location_data
    
    return DzialIO(content=content, raw_html=html_content)


async def parse_dzial_isp(page: Page, html_content: str) -> DzialISp:
    """
    Parse data from Dział I-Sp section.
    
    Args:
        page: Playwright page object
        html_content: HTML content of the section
        
    Returns:
        DzialISp: Parsed data
    """
    content = {}
    
    # Extract table data
    tables = await page.query_selector_all("table.tabela-dane")
    
    if tables:
        property_data = []
        
        for table in tables:
            rows = await table.query_selector_all("tr")
            headers = []
            
            for i, row in enumerate(rows):
                cells = await row.query_selector_all("td")
                
                if i == 0:  # Header row
                    for cell in cells:
                        headers.append(await cell.inner_text())
                else:  # Data rows
                    row_data = {}
                    for j, cell in enumerate(cells):
                        if j < len(headers):
                            row_data[headers[j].strip()] = (await cell.inner_text()).strip()
                    if row_data:
                        property_data.append(row_data)
        
        content["property_data"] = property_data
    
    return DzialISp(content=content, raw_html=html_content)


async def parse_dzial_ii(page: Page, html_content: str) -> DzialII:
    """
    Parse data from Dział II section.
    
    Args:
        page: Playwright page object
        html_content: HTML content of the section
        
    Returns:
        DzialII: Parsed data
    """
    content = {}
    
    # Extract table data
    tables = await page.query_selector_all("table.tabela-dane")
    
    if tables:
        ownership_data = []
        
        for table in tables:
            rows = await table.query_selector_all("tr")
            headers = []
            
            for i, row in enumerate(rows):
                cells = await row.query_selector_all("td")
                
                if i == 0:  # Header row
                    for cell in cells:
                        headers.append(await cell.inner_text())
                else:  # Data rows
                    row_data = {}
                    for j, cell in enumerate(cells):
                        if j < len(headers):
                            row_data[headers[j].strip()] = (await cell.inner_text()).strip()
                    if row_data:
                        ownership_data.append(row_data)
        
        content["ownership_data"] = ownership_data
    
    return DzialII(content=content, raw_html=html_content)


async def parse_dzial_iii(page: Page, html_content: str) -> DzialIII:
    """
    Parse data from Dział III section.
    
    Args:
        page: Playwright page object
        html_content: HTML content of the section
        
    Returns:
        DzialIII: Parsed data
    """
    content = {}
    
    # Extract table data
    tables = await page.query_selector_all("table.tabela-dane")
    
    if tables:
        rights_data = []
        
        for table in tables:
            rows = await table.query_selector_all("tr")
            headers = []
            
            for i, row in enumerate(rows):
                cells = await row.query_selector_all("td")
                
                if i == 0:  # Header row
                    for cell in cells:
                        headers.append(await cell.inner_text())
                else:  # Data rows
                    row_data = {}
                    for j, cell in enumerate(cells):
                        if j < len(headers):
                            row_data[headers[j].strip()] = (await cell.inner_text()).strip()
                    if row_data:
                        rights_data.append(row_data)
        
        content["rights_data"] = rights_data
    
    return DzialIII(content=content, raw_html=html_content)


async def parse_dzial_iv(page: Page, html_content: str) -> DzialIV:
    """
    Parse data from Dział IV section.
    
    Args:
        page: Playwright page object
        html_content: HTML content of the section
        
    Returns:
        DzialIV: Parsed data
    """
    content = {}
    
    # Extract table data
    tables = await page.query_selector_all("table.tabela-dane")
    
    if tables:
        mortgage_data = []
        
        for table in tables:
            rows = await table.query_selector_all("tr")
            headers = []
            
            for i, row in enumerate(rows):
                cells = await row.query_selector_all("td")
                
                if i == 0:  # Header row
                    for cell in cells:
                        headers.append(await cell.inner_text())
                else:  # Data rows
                    row_data = {}
                    for j, cell in enumerate(cells):
                        if j < len(headers):
                            row_data[headers[j].strip()] = (await cell.inner_text()).strip()
                    if row_data:
                        mortgage_data.append(row_data)
        
        content["mortgage_data"] = mortgage_data
    
    return DzialIV(content=content, raw_html=html_content)


async def wait_for_element(page: Page, selector: str, timeout: int = 15000) -> bool:
    """
    Wait for an element to appear on the page.
    
    Args:
        page: Playwright page object
        selector: CSS selector for the element
        timeout: Timeout in milliseconds (default: 15000)
        
    Returns:
        bool: True if element appeared, False if timeout
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        return True
    except Exception as e:
        logger.warning(f"Timeout waiting for element {selector}: {str(e)}")
        return False
