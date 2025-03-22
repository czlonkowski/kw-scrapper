# EKW Scraper

A modern, asynchronous FastAPI application for scraping the Electronic Land and Mortgage Register (EKW) portal in Poland.

## Features

- **Direct Browser Automation**: Uses Playwright for reliable browser automation
- **Clean, Structured Data**: Extracts and cleans HTML content to return only structured data
- **Async API**: Built with FastAPI for high-performance asynchronous API endpoints
- **CLI Tool**: Includes a command-line interface for testing and direct usage
- **Type Safety**: Comprehensive type hints and Pydantic models throughout
- **Error Handling**: Robust error handling with detailed error messages

## Installation

### Prerequisites

- Python 3.10+
- pip (Python package manager)

### Setup

1. Clone the repository:

```bash
git clone https://github.com/czlonkowski/kw-scrapper.git
cd kw-scrapper
```

2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Install Playwright browsers:

```bash
playwright install chromium
```

5. Set up environment variables (create a `.env` file in the project root):

```
ekw_portal_url=https://przegladarka-ekw.ms.gov.pl/eukw_prz/KsiegiWieczyste/wyszukiwanieKW?komunikaty=true&kontakt=true&okienkoSerwisowe=false
MAX_CONCURRENT=5
```

### Docker Setup

You can also run the application using Docker:

1. Using pre-built image from GitHub Container Registry:

```bash
docker pull ghcr.io/czlonkowski/kw-scrapper:latest
```

> **Note:** The Docker image supports both AMD64 (x86_64) and ARM64 architectures, so it can run on various platforms including Apple M1/M2 Macs, AWS Graviton instances, and Raspberry Pi devices.

```bash
docker run -d -p 8000:8000 \
  -e ekw_portal_url=https://przegladarka-ekw.ms.gov.pl/eukw_prz/KsiegiWieczyste/wyszukiwanieKW?komunikaty=true&kontakt=true&okienkoSerwisowe=false \
  -e MAX_CONCURRENT=5 \
  ghcr.io/czlonkowski/kw-scrapper:latest
```

2. Using Docker Compose:

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  ekw-scraper:
    image: ghcr.io/czlonkowski/kw-scrapper:latest
    container_name: ekw-scraper
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - ekw_portal_url=https://przegladarka-ekw.ms.gov.pl/eukw_prz/KsiegiWieczyste/wyszukiwanieKW?komunikaty=true&kontakt=true&okienkoSerwisowe=false
      - MAX_CONCURRENT=5
      - LOG_LEVEL=INFO
    volumes:
      - ./logs:/app/logs
```

Then run:

```bash
docker-compose up -d
```

3. Building the image locally:

```bash
# Clone the repository
git clone https://github.com/czlonkowski/kw-scrapper.git
cd kw-scrapper

# Build and run with Docker Compose
docker-compose -f docker-compose.yml up -d --build
```

The API will be available at http://localhost:8000/docs

## Usage

### CLI Tool

The CLI tool allows you to quickly test the scraper with a specific KW number:

```bash
python cli.py --kod PO1G --numer 00012346 --cyfra 5 --output result.json
```

Parameters:
- `--kod`: Department code (e.g., PO1G)
- `--numer`: Land register number (e.g., 00012346)
- `--cyfra`: Check digit (e.g., 5)
- `--output`: Optional output file path to save results

### API Server

Start the FastAPI server:

```bash
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000.

#### API Endpoints

- **POST /api/scraper/ekw**
  - Scrapes the EKW portal for the given KW number
  - Request body:
    ```json
    {
      "kod_wydzialu": "PO1G",
      "numer_ksiegi_wieczystej": "00012346",
      "cyfra_kontrolna": "5"
    }
    ```
  - Query parameters:
    - `clean_html`: Boolean (default: true) - Whether to clean HTML from the response data

- **GET /api/scraper/health**
  - Health check endpoint
  - Returns: `{"status": "ok", "service": "ekw-scraper"}`

### Interactive API Documentation

When the server is running, you can access the interactive API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
kw-scrapper/
├── app/
│   ├── api/
│   │   └── routes/
│   │       └── scraper.py       # API routes
│   ├── core/
│   │   └── scraper.py           # Core scraping functionality
│   ├── models/
│   │   ├── request.py           # Request models
│   │   └── response.py          # Response models
│   ├── utils/
│   │   ├── browser.py           # Browser utilities
│   │   └── html_cleaner.py      # HTML cleaning utilities
│   ├── config.py                # Application configuration
│   └── main.py                  # FastAPI application
├── cli.py                       # Command-line interface
├── requirements.txt             # Project dependencies
└── README.md                    # Project documentation
```

## Response Structure

The scraper returns structured data for each section of the KW document:

```json
{
  "success": true,
  "error": null,
  "kw_number": "PO1G/00012346/5",
  "dzial_io": {
    "content": {
      "title": "DZIAŁ I-O - OZNACZENIE NIERUCHOMOŚCI",
      "tables": [...],
      "document_basis": [...]
    }
  },
  "dzial_isp": {
    "content": {
      "title": "DZIAŁ I-SP - SPIS PRAW ZWIĄZANYCH Z WŁASNOŚCIĄ",
      "tables": [...],
      "document_basis": [...]
    }
  },
  "dzial_ii": {
    "content": {
      "title": "DZIAŁ II - WŁASNOŚĆ",
      "tables": [...],
      "document_basis": [...]
    }
  },
  "dzial_iii": {
    "content": {
      "title": "DZIAŁ III - PRAWA, ROSZCZENIA I OGRANICZENIA",
      "tables": [...],
      "document_basis": [...]
    }
  },
  "dzial_iv": {
    "content": {
      "title": "DZIAŁ IV - HIPOTEKA",
      "tables": [...],
      "document_basis": [...]
    }
  }
}
```

## Error Handling

The scraper handles various error scenarios:

- Network connectivity issues
- Invalid KW numbers
- Changes in the EKW portal structure
- Session timeouts

Error responses include detailed error messages to help diagnose issues.

## Development

### Adding New Features

1. Create a new branch for your feature
2. Implement the feature with appropriate tests
3. Submit a pull request

### Running Tests

```bash
pytest
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is intended for legitimate data access purposes only. Users are responsible for ensuring compliance with the terms of service of the EKW portal and relevant laws regarding data access and usage.
