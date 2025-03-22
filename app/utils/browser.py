"""
Browser management utilities for EKW Scraper.
"""
import asyncio
from typing import Dict, Optional, Any
from playwright.async_api import async_playwright, Browser, Page, Playwright
import json

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
    Click element and wait for network idle with enhanced retry mechanism.
    Handles both visible elements and form submissions.
    
    Args:
        page: Page instance
        selector: CSS selector for element to click
        
    Returns:
        bool: True if successful, False otherwise
    """
    max_retries = 5
    retry_count = 0
    
    # Special handling for the critical 'Przeglądanie aktualnej treści KW' button
    is_critical_button = selector == "#przyciskWydrukZwykly"
    
    while retry_count < max_retries:
        try:
            # For the special case of the 'Przeglądanie aktualnej treści KW' button
            if is_critical_button:
                # Take a screenshot before attempting interaction
                try:
                    await page.screenshot(path="debug_before_form_submit.png")
                except Exception:
                    pass
                
                # First, check if we're already on the content page
                content_indicators = [
                    'input[title="Dział I-O"]', 
                    'a:has-text("Dział I-O")',
                    'div:has-text("TREŚĆ KSIĘGI WIECZYSTEJ")',
                    'table.tresc',
                    'frame[name="ramka"]'
                ]
                
                for indicator in content_indicators:
                    try:
                        element = await page.query_selector(indicator)
                        if element:
                            print(f"Already on KW content page (detected {indicator})")
                            return True
                    except Exception:
                        pass
                
                # Capture form data first
                form_data = await page.evaluate("""() => {
                    try {
                        // Find the form with ID 'command'
                        const form = document.getElementById('command');
                        if (!form) return { success: false, error: 'Form not found' };
                        
                        // Get the form action
                        const action = form.action;
                        
                        // Get the input values
                        const inputs = {};
                        const allInputs = form.querySelectorAll('input');
                        for (const input of allInputs) {
                            if (input.name) {
                                inputs[input.name] = input.value;
                            }
                        }
                        
                        return {
                            success: true,
                            action,
                            method: form.method,
                            inputs
                        };
                    } catch (error) {
                        return { success: false, error: error.toString() };
                    }
                }""")
                
                print(f"Form data: {json.dumps(form_data, indent=2)}")
                
                # If form not found, try to find the button directly
                if not form_data.get('success', False):
                    print("Form not found, looking for button directly")
                    
                    # Check if the button exists
                    button_exists = await page.evaluate("""() => {
                        const button = document.querySelector('#przyciskWydrukZwykly');
                        return !!button;
                    }""")
                    
                    if not button_exists:
                        print("Button not found by ID, looking for any button with relevant text")
                        
                        # Look for any button with relevant text
                        button_info = await page.evaluate("""() => {
                            const buttons = document.querySelectorAll('button, input[type="submit"], a');
                            for (const btn of buttons) {
                                const text = (btn.textContent || btn.value || '').trim();
                                if (text.includes('Przeglądanie') || text.includes('treści KW')) {
                                    return {
                                        found: true,
                                        text: text,
                                        id: btn.id,
                                        tag: btn.tagName,
                                        classes: btn.className
                                    };
                                }
                            }
                            return { found: false };
                        }""")
                        
                        print(f"Button search result: {json.dumps(button_info, indent=2)}")
                        
                        if button_info.get('found', False):
                            # Try to click this button
                            try:
                                if button_info.get('id'):
                                    print(f"Clicking button with ID: #{button_info['id']}")
                                    await page.click(f"#{button_info['id']}")
                                elif button_info.get('tag') and button_info.get('text'):
                                    print(f"Clicking {button_info['tag']} with text: {button_info['text']}")
                                    await page.click(f"{button_info['tag']}:has-text('{button_info['text']}')")
                                
                                # Wait for navigation
                                await page.wait_for_load_state("networkidle", timeout=30000)
                                
                                # Check if we reached the content page
                                for indicator in content_indicators:
                                    try:
                                        element = await page.query_selector(indicator)
                                        if element:
                                            print(f"Successfully reached KW content page via text button (detected {indicator})")
                                            return True
                                    except Exception:
                                        pass
                            except Exception as btn_click_error:
                                print(f"Error clicking found button: {str(btn_click_error)}")
                    
                    # If we still haven't found the content page, try to extract KW info from the page
                    kw_info = await page.evaluate("""() => {
                        try {
                            // Try to find KW number in the page
                            const elements = document.querySelectorAll('*');
                            for (const el of elements) {
                                const text = el.textContent || '';
                                if (text.includes('/')) {
                                    const match = text.match(/([A-Z0-9]{4})\/([0-9]+)\/([0-9]+)/);
                                    if (match) {
                                        return {
                                            kod: match[1],
                                            nr: match[2].padStart(8, '0'),  // Ensure 8 digits with leading zeros
                                            cyfra: match[3]
                                        };
                                    }
                                }
                            }
                            
                            // If not found in text, try to find in input fields
                            const kodInput = document.querySelector('#kodWydzialuInput');
                            const nrInput = document.querySelector('#numerKsiegiWieczystej');
                            const cyfraInput = document.querySelector('#cyfraKontrolna');
                            
                            if (kodInput && nrInput && cyfraInput) {
                                return {
                                    kod: kodInput.value,
                                    nr: nrInput.value.padStart(8, '0'),  // Ensure 8 digits with leading zeros
                                    cyfra: cyfraInput.value
                                };
                            }
                            
                            return null;
                        } catch (error) {
                            console.error('Error extracting KW info:', error);
                            return null;
                        }
                    }""")
                    
                    if kw_info:
                        print(f"Extracted KW info from page: {json.dumps(kw_info, indent=2)}")
                    else:
                        print("Could not extract KW info from page")
                        # If we can't extract KW info, use the form data if available
                        if form_data.get('success', False) and form_data.get('inputs', {}):
                            kw_info = {
                                'kod': form_data['inputs'].get('kodWydzialu', ''),
                                'nr': form_data['inputs'].get('nrKw', ''),
                                'cyfra': form_data['inputs'].get('cyfraK', ''),
                                'uuid': form_data['inputs'].get('uuid', '')
                            }
                            print(f"Using KW info from form data: {json.dumps(kw_info, indent=2)}")
                else:
                    # Extract KW information from form data
                    kw_info = {
                        'kod': form_data['inputs'].get('kodWydzialu', ''),
                        'nr': form_data['inputs'].get('nrKw', ''),
                        'cyfra': form_data['inputs'].get('cyfraK', ''),
                        'uuid': form_data['inputs'].get('uuid', '')
                    }
                    
                    print(f"Extracted KW info from form: {json.dumps(kw_info, indent=2)}")
                
                # Now try a direct approach to reach the content page
                if kw_info and kw_info.get('kod') and kw_info.get('nr') and kw_info.get('cyfra'):
                    try:
                        # Try direct URL navigation first (most reliable)
                        print("Trying direct URL navigation to content page")
                        
                        # Try different URL patterns
                        urls_to_try = [
                            f"https://przegladarka-ekw.ms.gov.pl/eukw_prz/KsiegiWieczyste/pokazWydruk?kodWydzialu={kw_info['kod']}&nrKw={kw_info['nr']}&cyfraK={kw_info['cyfra']}&przyciskWydrukZwykly=",
                            f"https://przegladarka-ekw.ms.gov.pl/eukw_prz/KsiegiWieczyste/pokazTresc?kodWydzialu={kw_info['kod']}&numerKw={kw_info['nr']}&cyfraKontrolna={kw_info['cyfra']}",
                            # Add more URL patterns if needed
                        ]
                        
                        for url in urls_to_try:
                            print(f"Trying direct navigation to: {url}")
                            try:
                                await page.goto(url, wait_until="networkidle", timeout=30000)
                                print(f"Successfully navigated to {url}")
                                
                                # Check if we've reached the content page
                                for indicator in content_indicators:
                                    try:
                                        element = await page.query_selector(indicator)
                                        if element:
                                            print(f"Successfully reached KW content page via direct URL (detected {indicator})")
                                            return True
                                    except Exception:
                                        pass
                                
                                # Take a screenshot of the current state
                                await page.screenshot(path="debug_after_direct_navigation.png")
                                
                                # If we didn't find content indicators, check for any errors or redirects
                                page_content = await page.content()
                                if "błąd" in page_content.lower() or "error" in page_content.lower():
                                    print("Error page detected after direct navigation")
                                    break  # Try next approach
                                
                            except Exception as e:
                                print(f"Navigation to {url} failed: {str(e)}")
                    
                    except Exception as url_error:
                        print(f"All direct URL navigation attempts failed: {str(url_error)}")
                
                # If direct navigation failed, try the button click approach
                if form_data.get('success', False):
                    try:
                        print("Trying button click approach")
                        
                        # First approach: Find and click the button directly with navigation handling
                        button = await page.query_selector('#przyciskWydrukZwykly')
                        if button:
                            print("Found button by ID, clicking it")
                            
                            # Set up a navigation promise
                            try:
                                async with page.expect_navigation(wait_until="networkidle", timeout=30000) as navigation_info:
                                    await page.click('#przyciskWydrukZwykly')
                                
                                # Wait for navigation to complete
                                await navigation_info.value
                                print("Button clicked and navigation completed")
                                
                                # Check if we've reached the target page
                                for indicator in content_indicators:
                                    try:
                                        element = await page.query_selector(indicator)
                                        if element:
                                            print(f"Successfully reached KW content page after button click (detected {indicator})")
                                            return True
                                    except Exception:
                                        pass
                            except Exception as nav_error:
                                print(f"Navigation error after button click: {str(nav_error)}")
                        else:
                            print("Button not found by ID")
                    
                    except Exception as button_error:
                        print(f"Button click approach failed: {str(button_error)}")
                
                # If all approaches failed, try JavaScript form submission
                try:
                    print("Trying JavaScript form submission")
                    
                    js_form_result = await page.evaluate("""(kwInfo) => {
                        try {
                            // Create a new form
                            const form = document.createElement('form');
                            form.method = 'POST';
                            form.action = 'https://przegladarka-ekw.ms.gov.pl/eukw_prz/KsiegiWieczyste/pokazWydruk';
                            
                            // Add the required hidden inputs
                            const addInput = (name, value) => {
                                const input = document.createElement('input');
                                input.type = 'hidden';
                                input.name = name;
                                input.value = value;
                                form.appendChild(input);
                            };
                            
                            addInput('kodWydzialu', kwInfo.kod);
                            addInput('nrKw', kwInfo.nr);
                            addInput('cyfraK', kwInfo.cyfra);
                            
                            if (kwInfo.uuid) {
                                addInput('uuid', kwInfo.uuid);
                            }
                            
                            // Add the button input
                            addInput('przyciskWydrukZwykly', '');
                            
                            // Add the form to the document and submit it
                            document.body.appendChild(form);
                            console.log('Submitting custom form');
                            form.submit();
                            
                            return { success: true };
                        } catch (error) {
                            return { success: false, error: error.toString() };
                        }
                    }""", kw_info)
                    
                    print(f"JavaScript form submission result: {json.dumps(js_form_result, indent=2)}")
                    
                    # Wait for navigation to complete
                    try:
                        await page.wait_for_load_state("networkidle", timeout=30000)
                        print("Navigation completed after JavaScript form submission")
                        
                        # Check if we've reached the target page
                        for indicator in content_indicators:
                            try:
                                element = await page.query_selector(indicator)
                                if element:
                                    print(f"Successfully reached KW content page after JS form submission (detected {indicator})")
                                    return True
                            except Exception:
                                pass
                    except Exception as nav_error:
                        print(f"Navigation error after JavaScript form submission: {str(nav_error)}")
                
                except Exception as js_form_error:
                    print(f"JavaScript form submission failed: {str(js_form_error)}")
                
                # If all else fails, try to restart from the search page
                try:
                    print("All approaches failed, restarting from search page")
                    
                    # Navigate to the search page
                    await page.goto(settings.ekw_portal_url, wait_until="networkidle", timeout=30000)
                    
                    # Wait for the form to be visible
                    await page.wait_for_selector('#kodWydzialuInput', state="visible", timeout=10000)
                    
                    # Fill the form with the KW number
                    if kw_info and kw_info.get('kod') and kw_info.get('nr') and kw_info.get('cyfra'):
                        await page.fill('#kodWydzialuInput', kw_info['kod'])
                        await page.fill('#numerKsiegiWieczystej', kw_info['nr'].lstrip('0'))  # Remove leading zeros
                        await page.fill('#cyfraKontrolna', kw_info['cyfra'])
                        
                        # Click the search button with navigation handling
                        async with page.expect_navigation(wait_until="networkidle", timeout=30000) as navigation_info:
                            await page.click('#wyszukaj')
                        
                        # Wait for navigation to complete
                        await navigation_info.value
                        
                        # Take a screenshot of the search results
                        await page.screenshot(path="debug_search_results.png")
                        
                        # Look for the button on the search results page
                        button_info = await page.evaluate("""() => {
                            const buttons = document.querySelectorAll('button, input[type="submit"], a');
                            for (const btn of buttons) {
                                const text = (btn.textContent || btn.value || '').trim();
                                if (text.includes('Przeglądanie') || text.includes('treści KW')) {
                                    return {
                                        found: true,
                                        text: text,
                                        id: btn.id,
                                        tag: btn.tagName,
                                        classes: btn.className
                                    };
                                }
                            }
                            return { found: false };
                        }""")
                        
                        print(f"Button search result on search page: {json.dumps(button_info, indent=2)}")
                        
                        if button_info.get('found', False):
                            # Try to click this button
                            try:
                                if button_info.get('id'):
                                    print(f"Clicking button with ID: #{button_info['id']}")
                                    
                                    async with page.expect_navigation(wait_until="networkidle", timeout=30000) as navigation_info:
                                        await page.click(f"#{button_info['id']}")
                                    
                                    # Wait for navigation to complete
                                    await navigation_info.value
                                    
                                elif button_info.get('tag') and button_info.get('text'):
                                    print(f"Clicking {button_info['tag']} with text: {button_info['text']}")
                                    
                                    async with page.expect_navigation(wait_until="networkidle", timeout=30000) as navigation_info:
                                        # Use JavaScript to click the button by text
                                        await page.evaluate(f"""() => {{
                                            const buttons = document.querySelectorAll('{button_info['tag']}');
                                            for (const btn of buttons) {{
                                                const text = (btn.textContent || btn.value || '').trim();
                                                if (text.includes('{button_info['text']}')) {{
                                                    btn.click();
                                                    return true;
                                                }}
                                            }}
                                            return false;
                                        }}""")
                                    
                                    # Wait for navigation to complete
                                    await navigation_info.value
                                
                                # Check if we reached the content page
                                for indicator in content_indicators:
                                    try:
                                        element = await page.query_selector(indicator)
                                        if element:
                                            print(f"Successfully reached KW content page via search page button (detected {indicator})")
                                            return True
                                    except Exception:
                                        pass
                            except Exception as btn_click_error:
                                print(f"Error clicking found button on search page: {str(btn_click_error)}")
                    
                except Exception as restart_error:
                    print(f"Restart from search page failed: {str(restart_error)}")
                
                # If we've tried everything and still failed, raise an exception to trigger retry
                raise Exception("Failed to reach KW content page after all approaches")
            
            else:
                # Standard approach for visible elements
                element = await page.wait_for_selector(selector, state="visible", timeout=10000)
                
                if element is None:
                    raise Exception(f"Element {selector} not found")
                    
                # Wait for stability
                await asyncio.sleep(0.5)
                
                # Click the element with navigation handling
                async with page.expect_navigation(wait_until="networkidle", timeout=20000) as navigation_info:
                    await page.click(selector)
                
                # Wait for navigation to complete
                try:
                    await navigation_info.value
                except Exception:
                    # If no navigation occurred, just wait for network idle
                    await page.wait_for_load_state("networkidle", timeout=20000)
                
                return True
                
        except Exception as e:
            retry_count += 1
            error_msg = f"Click attempt {retry_count}/{max_retries} failed for {selector}: {str(e)}"
            
            if retry_count >= max_retries:
                print(f"Error: {error_msg}")
                # Take a screenshot of the failure for debugging
                try:
                    await page.screenshot(path=f"debug_click_failure_{selector.replace('#', '')}.png")
                except Exception:
                    pass  # Ignore screenshot errors
                return False
            
            print(f"Warning: {error_msg}. Retrying...")
            
            # Progressive backoff for retries
            await asyncio.sleep(1 + retry_count)
            
            # For critical buttons, try refreshing the page if we've had multiple failures
            if is_critical_button and retry_count >= 2:
                try:
                    # Navigate to the search page
                    await page.goto(settings.ekw_portal_url, wait_until="networkidle")
                    print("Navigated back to search page, retrying the whole process...")
                except Exception as reload_error:
                    print(f"Warning: Page reload failed: {str(reload_error)}")
    
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
