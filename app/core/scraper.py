"""
Core scraping functionality for EKW portal.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from playwright.async_api import Page, Browser

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
from bs4 import BeautifulSoup
import re

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
        try:
            await navigate_to_url(page, settings.ekw_portal_url)
            logger.info(f"Navigated to EKW portal: {settings.ekw_portal_url}")
        except Exception as e:
            logger.error(f"Error navigating to EKW portal: {str(e)}")
            return ScraperResponse(
                success=False,
                error=f"Error navigating to EKW portal: {str(e)}",
                kw_number=f"{request.kod_wydzialu}/{request.numer_ksiegi_wieczystej}/{request.cyfra_kontrolna}"
            )
        
        # Accept cookies if present (with shorter timeout)
        try:
            await accept_cookies(page)
            logger.info("Attempted to accept cookies if present")
        except Exception as e:
            logger.warning(f"Cookie acceptance failed, but continuing: {str(e)}")
        
        # Take a screenshot for debugging
        try:
            await page.screenshot(path="debug_initial_page.png")
            logger.info("Saved initial page screenshot for debugging")
        except Exception as e:
            logger.warning(f"Failed to save initial page screenshot: {str(e)}")
        
        # Fill in the KW number fields
        try:
            await fill_kw_form(page, request)
            logger.info(f"Filled KW form with: {request.kod_wydzialu}/{request.numer_ksiegi_wieczystej}/{request.cyfra_kontrolna}")
        except Exception as e:
            logger.error(f"Error filling KW form: {str(e)}")
            return ScraperResponse(
                success=False,
                error=f"Error filling KW form: {str(e)}",
                kw_number=f"{request.kod_wydzialu}/{request.numer_ksiegi_wieczystej}/{request.cyfra_kontrolna}"
            )
        
        # Click search button
        search_success = await click_element(page, "#wyszukaj")
        if not search_success:
            logger.error("Failed to click search button")
            return ScraperResponse(
                success=False,
                error="Failed to click search button",
                kw_number=f"{request.kod_wydzialu}/{request.numer_ksiegi_wieczystej}/{request.cyfra_kontrolna}"
            )
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
        view_success = await click_element(page, "#przyciskWydrukZwykly")
        if not view_success:
            logger.error("Failed to click on 'Przeglądanie aktualnej treści KW' button")
            return ScraperResponse(
                success=False,
                error="Failed to click on 'Przeglądanie aktualnej treści KW' button",
                kw_number=f"{request.kod_wydzialu}/{request.numer_ksiegi_wieczystej}/{request.cyfra_kontrolna}"
            )
        logger.info("Clicked on 'Przeglądanie aktualnej treści KW' button")
        
        # Process each section
        try:
            sections_data = await process_all_sections(page)
        except Exception as e:
            logger.error(f"Error processing sections: {str(e)}")
            return ScraperResponse(
                success=False,
                error=f"Error processing sections: {str(e)}",
                kw_number=f"{request.kod_wydzialu}/{request.numer_ksiegi_wieczystej}/{request.cyfra_kontrolna}"
            )
        
        # Clean HTML if requested
        if clean_html:
            try:
                sections_data = clean_scraped_data(sections_data)
                logger.info("Cleaned HTML from scraped data")
            except Exception as e:
                logger.warning(f"Failed to clean HTML: {str(e)}")
        
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
            section_data = await process_section(page, section_name, section_info["selector"])
            if section_data is not None:
                result[section_name] = section_data
        except Exception as e:
            logger.error(f"Error processing {section_name}: {str(e)}")
            # Create empty section data with error
            section_class = globals()[section_name.title().replace("_", "")]
            result[section_name] = section_class(
                content={"title": f"DZIAŁ {section_name.upper().replace('DZIAL_', '').replace('_', '-')}", "error": f"Failed to process section: {str(e)}"},
                raw_html=None
            )
    
    return result


async def process_section(page: Page, section_name: str, section_selector: str) -> Dict[str, Any]:
    """
    Process a specific section of the KW document.
    
    Args:
        page: Playwright page object
        section_name: Name of the section (e.g., 'dzial_ii')
        section_selector: CSS selector for the section button
        
    Returns:
        Dict: Parsed section data
    """
    try:
        # Click on section button
        click_success = await click_element(page, section_selector)
        if not click_success:
            logger.error(f"Failed to click on {section_name} button")
            return None
        
        logger.info(f"Clicked on {section_name} button")
        
        # Wait for section content to load
        await wait_for_element(page, "#contentDzialu")
        
        # Extract HTML content
        html_content = await extract_html_content(page, "#contentDzialu")
        
        # Parse section data
        parse_function = globals()[f"parse_{section_name}"]
        section_data = await parse_function(page, html_content)
        
        logger.info(f"Processed {section_name} successfully")
        return section_data
    
    except Exception as e:
        logger.error(f"Error processing {section_name}: {str(e)}")
        return None


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
    content = {"title": "DZIAŁ II - WŁASNOŚĆ", "tables": []}
    
    # Use BeautifulSoup for direct HTML parsing
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all owner rows by looking for cells containing PESEL numbers (11 digits)
    pesel_pattern = re.compile(r'\d{11}')
    owner_rows = []
    
    for td in soup.find_all('td'):
        if pesel_pattern.search(str(td.text)) and 'CZŁONKOWSK' in td.text:
            owner_row = td.parent
            owner_rows.append(owner_row)
    
    # Process each owner row to extract owner information
    for i, row in enumerate(owner_rows):
        # Extract owner information
        owner_info = row.find('td', text=lambda t: pesel_pattern.search(str(t)) and 'CZŁONKOWSK' in t)
        
        if owner_info:
            owner_data = {
                "Lista wskazań udziałów w prawie (numer udziału w prawie/ wielkość udziału/rodzaj wspólności)": str(i + 1),
                "Osoba fizyczna (Imię pierwsze nazwisko, imię ojca, imię matki, PESEL)": owner_info.text.strip()
            }
            
            # Try to find the Lp number in previous rows
            lp_row = None
            current_row = row
            
            # Look up to 5 rows back for Lp. X.
            for _ in range(5):
                if current_row.previous_sibling:
                    current_row = current_row.previous_sibling
                    if isinstance(current_row, Tag):
                        lp_cell = current_row.find('td', text=re.compile(r'Lp\. \d+\.'))
                        if lp_cell:
                            lp_match = re.search(r'Lp\. (\d+)\.', lp_cell.text)
                            if lp_match:
                                owner_data["Lp. " + lp_match.group(1) + "."] = lp_match.group(1)
                                break
            
            content["tables"].append(owner_data)
    
    # If BeautifulSoup parsing failed, try a JavaScript approach
    if not content["tables"]:
        # Use a JavaScript approach to extract owners
        owners = await page.evaluate("""
        () => {
            try {
                const owners = [];
                
                // Find all elements containing PESEL numbers
                const peselElements = Array.from(document.querySelectorAll('td'))
                    .filter(td => td.textContent.match(/\\d{11}/) && 
                                td.textContent.includes('CZŁONKOWSK'));
                
                for (let i = 0; i < peselElements.length; i++) {
                    const peselElement = peselElements[i];
                    const ownerData = {
                        "Lista wskazań udziałów w prawie (numer udziału w prawie/ wielkość udziału/rodzaj wspólności)": String(i + 1),
                        "Osoba fizyczna (Imię pierwsze nazwisko, imię ojca, imię matki, PESEL)": peselElement.textContent.trim()
                    };
                    
                    // Try to find the Lp number
                    let currentRow = peselElement.closest('tr');
                    let previousRow = currentRow.previousElementSibling;
                    
                    while (previousRow) {
                        const lpMatch = previousRow.textContent.match(/Lp\\. (\\d+)\\./);
                        if (lpMatch) {
                            ownerData["Lp. " + lpMatch[1] + "."] = lpMatch[1];
                            break;
                        }
                        previousRow = previousRow.previousElementSibling;
                    }
                    
                    owners.push(ownerData);
                }
                
                return owners;
            } catch (error) {
                console.error("Error extracting owners:", error);
                return [];
            }
        }
        """)
        
        if owners and isinstance(owners, list):
            content["tables"] = owners
    
    # Extract document basis information
    basis_docs = await extract_document_basis(page)
    if basis_docs:
        content["document_basis"] = basis_docs
    
    return DzialII(content=content, raw_html=None)


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


async def extract_document_basis(page: Page) -> List[Dict[str, str]]:
    """
    Extract document basis information from a section.
    
    Args:
        page: Playwright page object
        
    Returns:
        List[Dict[str, str]]: Document basis information
    """
    basis_docs = []
    
    # Find the document basis section
    basis_tables = await page.query_selector_all("table.tabelaOpisnaPodstawaWpisu")
    
    for table in basis_tables:
        rows = await table.query_selector_all("tr")
        if len(rows) < 2:
            continue
            
        basis_number = None
        document_description = None
        journal_info = None
        
        for row in rows:
            cells = await row.query_selector_all("td")
            if len(cells) < 2:
                continue
                
            header_cell = cells[0]
            value_cell = cells[1]
            
            header_text = (await header_cell.inner_text()).strip()
            value_text = (await value_cell.inner_text()).strip()
            
            if "Numer podstawy wpisu" in header_text:
                basis_number = value_text
            elif document_description is None and basis_number is not None:
                document_description = value_text
            elif journal_info is None and document_description is not None:
                journal_info = value_text
        
        if basis_number:
            basis_docs.append({
                "basis_number": basis_number,
                "document_description": document_description if document_description else "",
                "journal_info": journal_info if journal_info else ""
            })
    
    return basis_docs


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


async def debug_parse_dzial_ii(html_path: str, browser: Browser) -> Dict[str, Any]:
    """
    Debug function to test Dział II parsing with a saved HTML file
    
    Args:
        html_path: Path to the saved HTML file
        browser: Playwright browser instance
        
    Returns:
        Dict: Parsed data structure
    """
    # Read the HTML file
    with open(html_path, "r") as f:
        html_content = f.read()
    
    # Create a new page to evaluate JavaScript on
    page = await browser.new_page()
    
    # Set the content of the page to the saved HTML
    await page.set_content(html_content)
    
    # Extract owner information using JavaScript
    owners = await page.evaluate("""
    () => {
        const owners = [];
        
        // Find all elements containing PESEL numbers
        const elements = Array.from(document.querySelectorAll('td'));
        const ownerElements = elements.filter(el => 
            el.textContent.match(/\\d{11}/) && 
            el.textContent.includes('CZŁONKOWSK')
        );
        
        for (const el of ownerElements) {
            owners.push({
                "Osoba fizyczna (Imię pierwsze nazwisko, imię ojca, imię matki, PESEL)": el.textContent.trim()
            });
        }
        
        return owners;
    }
    """)
    
    if owners and isinstance(owners, list):
        for i, owner in enumerate(owners):
            owner["Lista wskazań udziałów w prawie (numer udziału w prawie/ wielkość udziału/rodzaj wspólności)"] = str(i + 1)
    # Close the page
    await page.close()
    
    # Return the content structure
    return {"title": "DZIAŁ II - WŁASNOŚĆ", "tables": owners}
