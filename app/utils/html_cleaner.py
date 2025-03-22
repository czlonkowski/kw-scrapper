"""
Utility functions for cleaning HTML content from scraped data.
"""
import re
from typing import Dict, Any, List, Union
import html
from bs4 import BeautifulSoup
from pydantic import BaseModel


def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace and normalizing.
    
    Args:
        text: Text to clean
        
    Returns:
        str: Cleaned text
    """
    if not text:
        return ""
    
    # Decode HTML entities
    text = html.unescape(text)
    
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


def extract_text_from_html(html_content: str) -> str:
    """
    Extract plain text from HTML content.
    
    Args:
        html_content: HTML content
        
    Returns:
        str: Plain text
    """
    if not html_content:
        return ""
    
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.extract()
    
    # Get text
    text = soup.get_text()
    
    # Clean text
    return clean_text(text)


def extract_table_data(html_content: str) -> List[Dict[str, str]]:
    """
    Extract structured data from HTML tables.
    
    Args:
        html_content: HTML content containing tables
        
    Returns:
        List[Dict[str, str]]: Extracted table data
    """
    if not html_content:
        return []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    tables = soup.select('table.tbOdpis')
    
    result = []
    
    for table in tables:
        rows = table.select('tr')
        if not rows:
            continue
        
        table_data = {}
        
        for row in rows:
            # Skip empty rows or title rows
            if not row.select('td.csDane') and not row.select('td.csBDane'):
                continue
            
            # Get key cells (usually the first cell in the row)
            key_cells = row.select('td.csDane')
            if not key_cells:
                continue
            
            # Get value cells (usually the second cell in the row)
            value_cells = row.select('td.csBDane')
            if not value_cells and len(key_cells) > 1:
                value_cells = [key_cells[1]]
                key_cells = [key_cells[0]]
            
            if key_cells and (value_cells or len(key_cells) > 1):
                key = clean_text(key_cells[0].get_text())
                
                # Skip empty keys
                if not key:
                    continue
                
                # Get value
                if value_cells:
                    value = clean_text(value_cells[0].get_text())
                elif len(key_cells) > 1:
                    value = clean_text(key_cells[1].get_text())
                else:
                    value = ""
                
                table_data[key] = value
        
        if table_data:
            result.append(table_data)
    
    return result


def extract_section_title(html_content: str) -> str:
    """
    Extract section title from HTML content.
    
    Args:
        html_content: HTML content
        
    Returns:
        str: Section title
    """
    if not html_content:
        return ""
    
    soup = BeautifulSoup(html_content, 'html.parser')
    title_elem = soup.select_one('td.csTTytul')
    
    if title_elem:
        return clean_text(title_elem.get_text())
    
    return ""


def parse_ekw_section(html_content: str) -> Dict[str, Any]:
    """
    Parse EKW section content into structured data.
    
    Args:
        html_content: HTML content of the section
        
    Returns:
        Dict[str, Any]: Structured data
    """
    if not html_content:
        return {}
    
    result = {}
    
    # Extract section title
    section_title = extract_section_title(html_content)
    if section_title:
        result["title"] = section_title
    
    # Extract tables data
    tables_data = extract_table_data(html_content)
    if tables_data:
        result["tables"] = tables_data
    
    # Extract document basis information
    basis_info = extract_document_basis(html_content)
    if basis_info:
        result["document_basis"] = basis_info
    
    return result


def extract_document_basis(html_content: str) -> List[Dict[str, str]]:
    """
    Extract document basis information from HTML content.
    
    Args:
        html_content: HTML content
        
    Returns:
        List[Dict[str, str]]: Document basis information
    """
    if not html_content:
        return []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the document basis section
    basis_title = soup.find('td', class_='csTTytul', string=lambda s: 'DOKUMENTY BĘDĄCE PODSTAWĄ WPISU' in s if s else False)
    if not basis_title:
        return []
    
    basis_table = basis_title.find_parent('table')
    if not basis_table:
        return []
    
    result = []
    current_basis = {}
    
    rows = basis_table.select('tr')
    for row in rows:
        # Skip title rows
        if row.select('td.csTTytul'):
            continue
        
        # Check if this is a new basis entry
        basis_num_cell = row.select_one('td[rowspan="2"]')
        if basis_num_cell:
            if current_basis:
                result.append(current_basis)
                current_basis = {}
            
            basis_num = clean_text(basis_num_cell.get_text())
            current_basis["basis_number"] = basis_num
            
            # Get document description
            desc_cell = row.select_one('td.csNDBDane')
            if desc_cell:
                current_basis["document_description"] = clean_text(desc_cell.get_text())
        
        # Check if this is the second row of a basis entry (contains journal info)
        journal_cell = row.select_one('td.csDane:not([rowspan])')
        if journal_cell and current_basis and not row.select('td[rowspan]'):
            current_basis["journal_info"] = clean_text(journal_cell.get_text())
    
    # Add the last basis entry if exists
    if current_basis:
        result.append(current_basis)
    
    return result


def clean_section_data(section_data: Any) -> Dict[str, Any]:
    """
    Clean section data by parsing and structuring the raw HTML.
    
    Args:
        section_data: Dictionary or Pydantic model containing section data with raw_html
        
    Returns:
        Dict[str, Any]: Cleaned and structured section data
    """
    # Convert Pydantic model to dict if needed
    if isinstance(section_data, BaseModel):
        section_dict = section_data.model_dump()
    else:
        section_dict = section_data
    
    cleaned_data = {}
    
    # If the section has raw_html, parse it
    if "raw_html" in section_dict and section_dict["raw_html"]:
        parsed_data = parse_ekw_section(section_dict["raw_html"])
        cleaned_data["content"] = parsed_data
    elif "content" in section_dict:
        # If content is already a dictionary, clean its values
        if isinstance(section_dict["content"], dict):
            cleaned_content = {}
            for key, value in section_dict["content"].items():
                if isinstance(value, str):
                    cleaned_content[key] = clean_text(value)
                elif isinstance(value, list):
                    if all(isinstance(item, dict) for item in value):
                        cleaned_content[key] = [
                            {k: clean_text(v) if isinstance(v, str) else v for k, v in item.items()}
                            for item in value
                        ]
                    else:
                        cleaned_content[key] = value
                else:
                    cleaned_content[key] = value
            cleaned_data["content"] = cleaned_content
        else:
            cleaned_data["content"] = section_dict["content"]
    
    # Copy other fields except raw_html
    for key, value in section_dict.items():
        if key != "raw_html" and key != "content":
            cleaned_data[key] = value
    
    return cleaned_data


def clean_scraped_data(data: Any) -> Dict[str, Any]:
    """
    Clean all scraped data by parsing HTML and creating structured data.
    
    Args:
        data: Dictionary or Pydantic model containing scraped data
        
    Returns:
        Dict[str, Any]: Cleaned and structured data
    """
    if not data:
        return {}
    
    # Convert Pydantic model to dict if needed
    if isinstance(data, BaseModel):
        data_dict = data.model_dump()
    else:
        data_dict = data
    
    result = {}
    
    # Clean each section
    for key, value in data_dict.items():
        if key.startswith("dzial_") and value:
            result[key] = clean_section_data(value)
        else:
            result[key] = value
    
    return result


def clean_html_content(html_content: str) -> str:
    """
    Clean HTML content by removing unnecessary elements and normalizing structure.
    
    Args:
        html_content: Raw HTML content
        
    Returns:
        str: Cleaned HTML content
    """
    if not html_content:
        return ""
    
    try:
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'meta', 'link', 'iframe']):
            element.decompose()
            
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, str) and text.strip().startswith('<!--')):
            comment.extract()
            
        # Remove hidden elements
        for element in soup.find_all(style=lambda value: value and 'display:none' in value):
            element.decompose()
            
        # Remove empty elements
        for element in soup.find_all():
            if len(element.get_text(strip=True)) == 0 and not element.find_all(['img']):
                if element.name not in ['br', 'hr', 'img', 'input', 'meta']:
                    element.decompose()
        
        # Normalize whitespace in text nodes
        for text in soup.find_all(text=True):
            if text.parent.name not in ['style', 'script', 'pre', 'code']:
                text.replace_with(re.sub(r'\s+', ' ', text.strip()))
        
        # Get the cleaned HTML
        cleaned_html = str(soup)
        
        # Remove excessive newlines
        cleaned_html = re.sub(r'\n{3,}', '\n\n', cleaned_html)
        
        return cleaned_html
    
    except Exception as e:
        # If parsing fails, return the original HTML with minimal cleaning
        return re.sub(r'\s+', ' ', html_content).strip()
