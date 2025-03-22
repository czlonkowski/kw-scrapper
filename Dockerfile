FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright with specific architecture handling
RUN pip install --no-cache-dir playwright && \
    if [ "$(uname -m)" = "aarch64" ]; then \
        # ARM64-specific installation
        playwright install --with-deps chromium; \
    else \
        # x86_64 installation
        playwright install chromium && \
        playwright install-deps chromium; \
    fi

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Create a non-root user to run the application
RUN useradd -m appuser
USER appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/api/scraper/health || exit 1

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
