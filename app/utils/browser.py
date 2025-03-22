"""
Browser management utilities for EKW Scraper.
"""
import asyncio
from typing import Dict, Optional, Any
from playwright.async_api import async_playwright, Browser, Page, Playwright

from app.config import settings

async def initialize_browser() -> tuple[Playwright, Browser, Page]:
    """
    Initialize Playwright browser directly without using Bright Data.
    
    Returns:
        tuple: Playwright instance, Browser instance, and Page
    """
    playwright = await async_playwright().start()
    
    # Launch a browser directly
    browser = await playwright.chromium.launch(
        headless=True,  # Set to False for debugging
        slow_mo=100  # Slow down operations by 100ms for stability
    )
    
    # Create a new browser context with specific options
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )
    
    # Create a new page
    page = await context.new_page()
    
    # Set longer timeouts for navigation and actions
    page.set_default_navigation_timeout(60000)  # 60 seconds
    page.set_default_timeout(60000)  # 60 seconds
    
    return playwright, browser, page

async def close_browser(playwright: Playwright, browser: Browser) -> None:
    """
    Close browser and Playwright instance.
    
    Args:
        playwright: Playwright instance
        browser: Browser instance
    """
    await browser.close()
    await playwright.stop()

async def navigate_to_url(page: Page, url: str) -> None:
    """
    Navigate to URL and wait for network idle.
    
    Args:
        page: Page instance
        url: URL to navigate to
    """
    await page.goto(url, wait_until="networkidle")

async def fill_input(page: Page, selector: str, value: str) -> None:
    """
    Fill input field with value.
    
    Args:
        page: Page instance
        selector: CSS selector for input field
        value: Value to input
    """
    await page.fill(selector, value)

async def click_element(page: Page, selector: str) -> bool:
    """
    Click element and wait for network idle with retry mechanism.
    
    Args:
        page: Page instance
        selector: CSS selector for element to click
        
    Returns:
        bool: True if successful, False otherwise
    """
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # First ensure element is visible
            await page.wait_for_selector(selector, state="visible", timeout=10000)
            
            # Wait a moment for stability
            await asyncio.sleep(0.5)
            
            # Try to click with a promise that resolves when navigation is complete
            await page.click(selector)
            
            # Wait for network to be idle
            await page.wait_for_load_state("networkidle", timeout=20000)
            
            return True
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                return False
            
            # Wait before retrying
            await asyncio.sleep(1)
    
    return False

async def wait_for_element(page: Page, selector: str, timeout: int = 30000) -> None:
    """
    Wait for element to be visible.
    
    Args:
        page: Page instance
        selector: CSS selector for element
        timeout: Timeout in milliseconds
    """
    await page.wait_for_selector(selector, state="visible", timeout=timeout)

async def get_element_text(page: Page, selector: str) -> str:
    """
    Get text content of element.
    
    Args:
        page: Page instance
        selector: CSS selector for element
        
    Returns:
        str: Text content of element
    """
    element = await page.query_selector(selector)
    if element:
        return await element.inner_text()
    return ""

async def get_elements_text(page: Page, selector: str) -> list[str]:
    """
    Get text content of multiple elements.
    
    Args:
        page: Page instance
        selector: CSS selector for elements
        
    Returns:
        list[str]: List of text content for each element
    """
    elements = await page.query_selector_all(selector)
    return [await element.inner_text() for element in elements]

async def extract_html_content(page: Page, selector: str = "body") -> str:
    """
    Extract HTML content from a specific element or the entire body.
    
    Args:
        page: Page instance
        selector: CSS selector for element (defaults to body)
        
    Returns:
        str: HTML content
    """
    element = await page.query_selector(selector)
    if element:
        return await element.inner_html()
    return ""

async def accept_cookies(page: Page) -> None:
    """
    Accept cookies on the page if a cookie consent dialog is present.
    
    Args:
        page: Page instance
    """
    # Common cookie consent button selectors
    cookie_button_selectors = [
        "button:has-text('Akceptuję')",
        "button:has-text('Zgadzam się')",
        "button:has-text('Zaakceptuj')",
        "button:has-text('Akceptuj')",
        "button:has-text('Accept')",
        "button:has-text('Accept all')",
        ".cookie-consent button",
        "#cookie-consent button",
        ".cookies-consent button",
        "#cookies-consent button",
        ".cookie-notice button",
        "#cookie-notice button",
        "#cookies-modal button",
        "div[id*='cookie'] button",
        "div[class*='cookie'] button"
    ]
    
    for selector in cookie_button_selectors:
        try:
            # Check if the button exists and is visible
            if await page.is_visible(selector):
                await page.click(selector)
                await page.wait_for_load_state("networkidle")
                return
        except Exception:
            continue
    
    # If no standard buttons found, try to find by content
    try:
        # Look for buttons with text related to accepting cookies
        buttons = await page.query_selector_all("button")
        for button in buttons:
            text = await button.inner_text()
            if any(keyword in text.lower() for keyword in ["akceptuj", "accept", "zgadzam", "zgoda"]):
                await button.click()
                await page.wait_for_load_state("networkidle")
                return
    except Exception:
        pass
