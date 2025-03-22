"""
Tests for the EKW scraper functionality.
"""
import pytest
import os
from unittest.mock import patch, AsyncMock

from app.models.request import KWRequest
from app.core.scraper import scrape_ekw
from app.models.response import ScraperResponse


@pytest.mark.asyncio
async def test_kw_request_model():
    """Test KWRequest model validation."""
    # Valid request
    request = KWRequest(
        kod_wydzialu="WA1M",
        numer_ksiegi_wieczystej="00533284",
        cyfra_kontrolna="3"
    )
    
    assert request.kod_wydzialu == "WA1M"
    assert request.numer_ksiegi_wieczystej == "00533284"
    assert request.cyfra_kontrolna == "3"


@pytest.mark.asyncio
@patch("app.core.scraper.initialize_browser")
@patch("app.core.scraper.close_browser")
@patch("app.core.scraper.navigate_to_url")
@patch("app.core.scraper.fill_kw_form")
@patch("app.core.scraper.click_element")
@patch("app.core.scraper.wait_for_element")
@patch("app.core.scraper.process_all_sections")
async def test_scrape_ekw_success(
    mock_process_all_sections,
    mock_wait_for_element,
    mock_click_element,
    mock_fill_kw_form,
    mock_navigate_to_url,
    mock_close_browser,
    mock_initialize_browser
):
    """Test successful scraping flow."""
    # Setup mocks
    mock_playwright = AsyncMock()
    mock_browser = AsyncMock()
    mock_page = AsyncMock()
    mock_initialize_browser.return_value = (mock_playwright, mock_browser, mock_page)
    
    mock_process_all_sections.return_value = {
        "dzial_io": {"content": {"test": "data"}, "raw_html": "<html>test</html>"},
        "dzial_isp": {"content": {"test": "data"}, "raw_html": "<html>test</html>"},
        "dzial_ii": {"content": {"test": "data"}, "raw_html": "<html>test</html>"},
        "dzial_iii": {"content": {"test": "data"}, "raw_html": "<html>test</html>"},
        "dzial_iv": {"content": {"test": "data"}, "raw_html": "<html>test</html>"}
    }
    
    # Execute
    request = KWRequest(
        kod_wydzialu="WA1M",
        numer_ksiegi_wieczystej="00533284",
        cyfra_kontrolna="3"
    )
    
    result = await scrape_ekw(request)
    
    # Assert
    assert isinstance(result, ScraperResponse)
    assert result.success is True
    assert result.kw_number == "WA1M/00533284/3"
    assert result.dzial_io is not None
    assert result.dzial_isp is not None
    assert result.dzial_ii is not None
    assert result.dzial_iii is not None
    assert result.dzial_iv is not None
    
    # Verify function calls
    mock_initialize_browser.assert_called_once()
    mock_navigate_to_url.assert_called_once()
    mock_fill_kw_form.assert_called_once_with(mock_page, request)
    mock_click_element.assert_called_with(mock_page, "#przyciskWydrukZwykly")
    mock_wait_for_element.assert_called_once()
    mock_process_all_sections.assert_called_once_with(mock_page)
    mock_close_browser.assert_called_once_with(mock_playwright, mock_browser)


@pytest.mark.asyncio
@patch("app.core.scraper.initialize_browser")
@patch("app.core.scraper.close_browser")
@patch("app.core.scraper.navigate_to_url")
@patch("app.core.scraper.fill_kw_form")
@patch("app.core.scraper.click_element")
@patch("app.core.scraper.wait_for_element")
@patch("app.core.scraper.get_error_message")
async def test_scrape_ekw_error(
    mock_get_error_message,
    mock_wait_for_element,
    mock_click_element,
    mock_fill_kw_form,
    mock_navigate_to_url,
    mock_close_browser,
    mock_initialize_browser
):
    """Test error handling during scraping."""
    # Setup mocks
    mock_playwright = AsyncMock()
    mock_browser = AsyncMock()
    mock_page = AsyncMock()
    mock_initialize_browser.return_value = (mock_playwright, mock_browser, mock_page)
    
    # Simulate error during wait_for_element
    mock_wait_for_element.side_effect = Exception("Element not found")
    mock_get_error_message.return_value = "Invalid KW number"
    
    # Execute
    request = KWRequest(
        kod_wydzialu="INVALID",
        numer_ksiegi_wieczystej="00000000",
        cyfra_kontrolna="0"
    )
    
    result = await scrape_ekw(request)
    
    # Assert
    assert isinstance(result, ScraperResponse)
    assert result.success is False
    assert "Invalid KW number" in result.error
    assert result.kw_number == "INVALID/00000000/0"
    
    # Verify function calls
    mock_initialize_browser.assert_called_once()
    mock_navigate_to_url.assert_called_once()
    mock_fill_kw_form.assert_called_once_with(mock_page, request)
    mock_click_element.assert_called_once()
    mock_wait_for_element.assert_called_once()
    mock_get_error_message.assert_called_once_with(mock_page)
    mock_close_browser.assert_called_once_with(mock_playwright, mock_browser)
