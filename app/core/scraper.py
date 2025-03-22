"""
Core scraping functionality for EKW portal.
"""
import asyncio
import logging
import json
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
from app.utils.html_cleaner import clean_scraped_data, clean_html_content, parse_ekw_section
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


async def scrape_ekw(request: KWRequest, clean_html: bool = True, save_screenshots: bool = False) -> ScraperResponse:
    """
    Scrape EKW portal for the given KW number.
    
    Args:
        request: KW request with kod_wydzialu, numer_ksiegi_wieczystej, and cyfra_kontrolna
        clean_html: Whether to clean HTML from scraped data
        save_screenshots: Whether to save screenshots for debugging purposes
        
    Returns:
        ScraperResponse with scraped data
    """
    playwright = None
    browser = None
    page = None
    
    try:
        # Format KW number
        kw_number = f"{request.kod_wydzialu}/{request.numer_ksiegi_wieczystej}/{request.cyfra_kontrolna}"
        logger.info(f"Starting EKW scraping for: {kw_number}")
        
        # Initialize browser
        playwright, browser, page = await initialize_browser()
        if not browser:
            return ScraperResponse(
                success=False,
                error="Failed to initialize browser",
                kw_number=kw_number
            )
        
        logger.info("Browser initialized successfully")
        
        # Navigate to EKW portal
        await page.goto(settings.ekw_portal_url, wait_until="networkidle")
        logger.info(f"Navigated to EKW portal: {settings.ekw_portal_url}")
        
        # Accept cookies if present
        try:
            cookie_button = page.locator('button:has-text("Akceptuję")')
            if await cookie_button.count() > 0:
                await cookie_button.click()
                await page.wait_for_load_state("networkidle")
            logger.info("Attempted to accept cookies if present")
        except Exception as e:
            logger.warning(f"Error accepting cookies: {str(e)}")
        
        # Save screenshot for debugging
        if save_screenshots:
            try:
                await page.screenshot(path=f"debug_initial_page_{request.kod_wydzialu}_{request.numer_ksiegi_wieczystej}_{request.cyfra_kontrolna}.png")
                logger.info("Saved initial page screenshot for debugging")
            except Exception as e:
                logger.warning(f"Failed to save initial page screenshot: {str(e)}")
        
        # Fill KW form
        await page.fill('#kodWydzialuInput', request.kod_wydzialu)
        await page.fill('#numerKsiegiWieczystej', request.numer_ksiegi_wieczystej.lstrip('0'))  # Remove leading zeros
        await page.fill('#cyfraKontrolna', request.cyfra_kontrolna)
        logger.info(f"Filled KW form with: {kw_number}")
        
        # Click search button
        await page.click('#wyszukaj')
        await page.wait_for_load_state("networkidle")
        logger.info("Clicked search button")
        
        # Check if search was successful (with timeout protection)
        try:
            komunikat_exists = await page.locator('.komunikat').count() > 0
            if komunikat_exists:
                error_msg = await page.locator('.komunikat').text_content(timeout=5000)
                if error_msg and "nie została odnaleziona" in error_msg:
                    return ScraperResponse(
                        success=False,
                        error=f"KW not found: {error_msg}",
                        kw_number=kw_number
                    )
        except Exception as e:
            # If we can't check for error message, just log and continue
            logger.warning(f"Error checking for komunikat: {str(e)}")
        
        logger.info("Search results loaded successfully")
        
        # Save screenshot for debugging
        if save_screenshots:
            try:
                await page.screenshot(path=f"debug_results_page_{request.kod_wydzialu}_{request.numer_ksiegi_wieczystej}_{request.cyfra_kontrolna}.png")
                logger.info("Saved results page screenshot for debugging")
            except Exception as e:
                logger.warning(f"Failed to save results page screenshot: {str(e)}")
        
        # Click on "Przeglądanie aktualnej treści KW" button
        if not await click_element(page, "#przyciskWydrukZwykly"):
            return ScraperResponse(
                success=False,
                error="Failed to click on 'Przeglądanie aktualnej treści KW' button",
                kw_number=kw_number
            )
        
        logger.info("Clicked on 'Przeglądanie aktualnej treści KW' button")
        
        # Save screenshot for debugging
        if save_screenshots:
            try:
                await page.screenshot(path=f"debug_content_page_{request.kod_wydzialu}_{request.numer_ksiegi_wieczystej}_{request.cyfra_kontrolna}.png")
                logger.info("Saved content page screenshot for debugging")
            except Exception as e:
                logger.warning(f"Failed to save content page screenshot: {str(e)}")
        
        # Check for frames
        frames = page.frames
        main_frame = page
        
        # Check if we have frames and find the main content frame
        if len(frames) > 1:
            logger.info(f"Found {len(frames)} frames on the page")
            for frame in frames:
                frame_name = frame.name
                frame_url = frame.url
                logger.info(f"Frame: {frame_name}, URL: {frame_url}")
                
                # Look for the content frame - it might be named 'ramka' or contain specific content
                if frame_name == 'ramka' or 'pokazTresc' in frame_url or 'pokazWydruk' in frame_url:
                    logger.info(f"Using frame: {frame_name} as main content frame")
                    main_frame = frame
                    break
        
        # Analyze the page structure to find the department buttons
        department_selectors = await main_frame.evaluate("""() => {
            // Look for different types of department buttons/links
            const selectors = {
                buttons: [],
                links: [],
                inputs: [],
                images: []
            };
            
            // Check for input buttons
            document.querySelectorAll('input[type="submit"], input[type="button"], button').forEach(el => {
                const value = el.value || el.textContent || '';
                const id = el.id || '';
                const classes = el.className || '';
                
                if (value.includes('Dział') || id.includes('dzial') || classes.includes('dzial')) {
                    selectors.buttons.push({
                        selector: el.tagName.toLowerCase() + (id ? `#${id}` : '') + (classes ? `.${classes.replace(/\\s+/g, '.')}` : ''),
                        type: el.tagName.toLowerCase(),
                        id: id,
                        value: value,
                        department: value.includes('I-O') ? 'io' : 
                                   value.includes('I-Sp') ? 'isp' : 
                                   value.includes('II') ? 'ii' : 
                                   value.includes('III') ? 'iii' : 
                                   value.includes('IV') ? 'iv' : null
                    });
                }
            });
            
            // Check for links
            document.querySelectorAll('a').forEach(el => {
                const text = el.textContent || '';
                const href = el.href || '';
                const id = el.id || '';
                const classes = el.className || '';
                
                if (text.includes('Dział') || href.includes('dzial') || id.includes('dzial') || classes.includes('dzial')) {
                    selectors.links.push({
                        selector: `a${id ? `#${id}` : ''}${classes ? `.${classes.replace(/\\s+/g, '.')}` : ''}`,
                        type: 'a',
                        id: id,
                        text: text,
                        href: href,
                        department: text.includes('I-O') ? 'io' : 
                                   text.includes('I-Sp') ? 'isp' : 
                                   text.includes('II') ? 'ii' : 
                                   text.includes('III') ? 'iii' : 
                                   text.includes('IV') ? 'iv' : null
                    });
                }
            });
            
            // Check for images that might be clickable department indicators
            document.querySelectorAll('img').forEach(el => {
                const alt = el.alt || '';
                const src = el.src || '';
                const id = el.id || '';
                
                if (alt.includes('Dział') || src.includes('dzial') || id.includes('dzial')) {
                    selectors.images.push({
                        selector: `img${id ? `#${id}` : ''}`,
                        type: 'img',
                        id: id,
                        alt: alt,
                        src: src,
                        department: alt.includes('I-O') ? 'io' : 
                                   alt.includes('I-Sp') ? 'isp' : 
                                   alt.includes('II') ? 'ii' : 
                                   alt.includes('III') ? 'iii' : 
                                   alt.includes('IV') ? 'iv' : null
                    });
                }
            });
            
            // Also check for any elements with text containing department names
            document.querySelectorAll('*').forEach(el => {
                const text = el.textContent || '';
                
                if (text.match(/Dział (I-O|I-Sp|II|III|IV)/) && 
                    !selectors.buttons.some(b => b.selector === el.tagName.toLowerCase()) && 
                    !selectors.links.some(l => l.selector === 'a') &&
                    !selectors.images.some(i => i.selector === 'img')) {
                    
                    selectors.inputs.push({
                        selector: el.tagName.toLowerCase(),
                        type: el.tagName.toLowerCase(),
                        text: text,
                        department: text.includes('I-O') ? 'io' : 
                                   text.includes('I-Sp') ? 'isp' : 
                                   text.includes('II') ? 'ii' : 
                                   text.includes('III') ? 'iii' : 
                                   text.includes('IV') ? 'iv' : null
                    });
                }
            });
            
            return selectors;
        }""")
        
        logger.info(f"Found department selectors: {json.dumps(department_selectors, indent=2)}")
        
        # Initialize response data
        dzial_io = None
        dzial_isp = None
        dzial_ii = None
        dzial_iii = None
        dzial_iv = None
        
        # Function to extract department content
        async def extract_department_content(frame, department_name):
            try:
                # Take a screenshot of the department content
                if save_screenshots:
                    try:
                        await page.screenshot(path=f"debug_{department_name}_content_{request.kod_wydzialu}_{request.numer_ksiegi_wieczystej}_{request.cyfra_kontrolna}.png")
                    except Exception:
                        pass
                
                # Extract the HTML content
                content_html = await frame.evaluate("""() => {
                    // Try to find the main content container
                    const contentContainers = [
                        document.querySelector('.tresc'),
                        document.querySelector('table.tresc'),
                        document.querySelector('div.content'),
                        document.querySelector('div[id*="content"]'),
                        document.querySelector('div[class*="content"]'),
                        document.querySelector('div[id*="tresc"]'),
                        document.querySelector('div[class*="tresc"]'),
                        // If none of the above, get the body content
                        document.body
                    ];
                    
                    // Use the first non-null container
                    const container = contentContainers.find(c => c !== null);
                    return container ? container.outerHTML : document.body.outerHTML;
                }""")
                
                return content_html
            except Exception as e:
                logger.error(f"Error extracting {department_name} content: {str(e)}")
                return None
        
        # Try to click each department button and extract content
        # First, try using the detected selectors
        departments_to_scrape = [
            ('io', 'dzial_io'),
            ('isp', 'dzial_isp'),
            ('ii', 'dzial_ii'),
            ('iii', 'dzial_iii'),
            ('iv', 'dzial_iv')
        ]
        
        for dept_code, dept_var in departments_to_scrape:
            # Try each type of selector (buttons, links, etc.)
            clicked = False
            
            # First try buttons
            for button in department_selectors.get('buttons', []):
                if button.get('department') == dept_code and button.get('selector'):
                    logger.info(f"Trying to click {dept_var} button with selector: {button['selector']}")
                    try:
                        await main_frame.click(button['selector'])
                        await page.wait_for_load_state("networkidle", timeout=5000)
                        logger.info(f"Clicked {dept_var} button")
                        clicked = True
                        break
                    except Exception as e:
                        logger.warning(f"Failed to click {dept_var} button with selector {button['selector']}: {str(e)}")
            
            # If button click failed, try links
            if not clicked:
                for link in department_selectors.get('links', []):
                    if link.get('department') == dept_code and link.get('selector'):
                        logger.info(f"Trying to click {dept_var} link with selector: {link['selector']}")
                        try:
                            await main_frame.click(link['selector'])
                            await page.wait_for_load_state("networkidle", timeout=5000)
                            logger.info(f"Clicked {dept_var} link")
                            clicked = True
                            break
                        except Exception as e:
                            logger.warning(f"Failed to click {dept_var} link with selector {link['selector']}: {str(e)}")
            
            # If link click failed, try images
            if not clicked:
                for img in department_selectors.get('images', []):
                    if img.get('department') == dept_code and img.get('selector'):
                        logger.info(f"Trying to click {dept_var} image with selector: {img['selector']}")
                        try:
                            await main_frame.click(img['selector'])
                            await page.wait_for_load_state("networkidle", timeout=5000)
                            logger.info(f"Clicked {dept_var} image")
                            clicked = True
                            break
                        except Exception as e:
                            logger.warning(f"Failed to click {dept_var} image with selector {img['selector']}: {str(e)}")
            
            # If all else failed, try JavaScript to find and click elements with department text
            if not clicked:
                logger.info(f"Trying JavaScript approach to click {dept_var}")
                try:
                    dept_name_map = {
                        'io': 'I-O',
                        'isp': 'I-Sp',
                        'ii': 'II',
                        'iii': 'III',
                        'iv': 'IV'
                    }
                    
                    dept_name = dept_name_map.get(dept_code, '')
                    
                    clicked_js = await main_frame.evaluate(f"""(deptName) => {{
                        // Try to find elements with the department name
                        const elements = Array.from(document.querySelectorAll('*'));
                        
                        for (const el of elements) {{
                            const text = el.textContent || el.value || el.alt || '';
                            const isClickable = el.tagName === 'A' || 
                                              el.tagName === 'BUTTON' || 
                                              el.tagName === 'INPUT' || 
                                              el.onclick || 
                                              el.role === 'button';
                            
                            if (text.includes(deptName) && isClickable) {{
                                console.log('Found clickable element for ' + deptName + ':', el);
                                el.click();
                                return true;
                            }}
                        }}
                        
                        return false;
                    }}""", dept_name)
                    
                    if clicked_js:
                        await page.wait_for_load_state("networkidle", timeout=5000)
                        logger.info(f"Clicked {dept_var} via JavaScript")
                        clicked = True
                except Exception as e:
                    logger.warning(f"JavaScript click for {dept_var} failed: {str(e)}")
            
            # Extract content if we successfully clicked
            if clicked:
                content = await extract_department_content(main_frame, dept_var)
                
                # Clean HTML if requested
                if clean_html and content:
                    cleaned_content = clean_html_content(content)
                    
                    # Create the appropriate department model instance with both raw and cleaned content
                    if dept_var == 'dzial_io':
                        dzial_io = DzialIO(content=parse_ekw_section(cleaned_content), raw_html=content if not clean_html else None)
                    elif dept_var == 'dzial_isp':
                        dzial_isp = DzialISp(content=parse_ekw_section(cleaned_content), raw_html=content if not clean_html else None)
                    elif dept_var == 'dzial_ii':
                        dzial_ii = DzialII(content=parse_ekw_section(cleaned_content), raw_html=content if not clean_html else None)
                    elif dept_var == 'dzial_iii':
                        dzial_iii = DzialIII(content=parse_ekw_section(cleaned_content), raw_html=content if not clean_html else None)
                    elif dept_var == 'dzial_iv':
                        dzial_iv = DzialIV(content=parse_ekw_section(cleaned_content), raw_html=content if not clean_html else None)
                else:
                    # If not cleaning, just store the raw HTML
                    if dept_var == 'dzial_io':
                        dzial_io = DzialIO(content={"title": "DZIAŁ I-O"}, raw_html=content)
                    elif dept_var == 'dzial_isp':
                        dzial_isp = DzialISp(content={"title": "DZIAŁ I-SP"}, raw_html=content)
                    elif dept_var == 'dzial_ii':
                        dzial_ii = DzialII(content={"title": "DZIAŁ II"}, raw_html=content)
                    elif dept_var == 'dzial_iii':
                        dzial_iii = DzialIII(content={"title": "DZIAŁ III"}, raw_html=content)
                    elif dept_var == 'dzial_iv':
                        dzial_iv = DzialIV(content={"title": "DZIAŁ IV"}, raw_html=content)
            else:
                logger.error(f"Failed to click on {dept_var} button")
        
        # If we couldn't click any department buttons, try to extract all content at once
        if not any([dzial_io, dzial_isp, dzial_ii, dzial_iii, dzial_iv]):
            logger.info("Attempting to extract all content at once")
            try:
                full_content = await main_frame.evaluate("""() => {
                    return document.body.outerHTML;
                }""")
                
                if clean_html:
                    cleaned_content = clean_html_content(full_content)
                    
                    # Create proper model instances for each department with parsed content
                    dzial_io = DzialIO(content=parse_ekw_section(cleaned_content), raw_html=full_content if not clean_html else None)
                    dzial_isp = DzialISp(content=parse_ekw_section(cleaned_content), raw_html=full_content if not clean_html else None)
                    dzial_ii = DzialII(content=parse_ekw_section(cleaned_content), raw_html=full_content if not clean_html else None)
                    dzial_iii = DzialIII(content=parse_ekw_section(cleaned_content), raw_html=full_content if not clean_html else None)
                    dzial_iv = DzialIV(content=parse_ekw_section(cleaned_content), raw_html=full_content if not clean_html else None)
                else:
                    # If not cleaning, just store the raw HTML
                    dzial_io = DzialIO(content={"title": "DZIAŁ I-O"}, raw_html=full_content)
                    dzial_isp = DzialISp(content={"title": "DZIAŁ I-SP"}, raw_html=full_content)
                    dzial_ii = DzialII(content={"title": "DZIAŁ II"}, raw_html=full_content)
                    dzial_iii = DzialIII(content={"title": "DZIAŁ III"}, raw_html=full_content)
                    dzial_iv = DzialIV(content={"title": "DZIAŁ IV"}, raw_html=full_content)
            except Exception as e:
                logger.error(f"Error extracting full content: {str(e)}")
        
        # Apply final cleaning to the response data if requested
        response = ScraperResponse(
            success=True,
            error=None,
            kw_number=kw_number,
            dzial_io=dzial_io,
            dzial_isp=dzial_isp,
            dzial_ii=dzial_ii,
            dzial_iii=dzial_iii,
            dzial_iv=dzial_iv
        )
        
        # Apply final data cleaning if requested
        if clean_html:
            logger.info("Applying final data cleaning")
            response = ScraperResponse(**clean_scraped_data(response))
            
        return response
    
    except Exception as e:
        logger.error(f"Error scraping EKW: {str(e)}")
        return ScraperResponse(
            success=False,
            error=f"Error scraping EKW: {str(e)}",
            kw_number=request.kod_wydzialu + "/" + request.numer_ksiegi_wieczystej + "/" + request.cyfra_kontrolna if request else "Unknown"
        )
    
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass
        
        if browser and playwright:
            try:
                await close_browser(playwright, browser)
                logger.info("Browser closed")
            except Exception:
                pass
