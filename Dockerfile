FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxtst6 \
    libnss3 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libxshmfence1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user to run the application
RUN useradd -m appuser

# Create cache directory for Playwright with proper permissions
RUN mkdir -p /home/appuser/.cache && \
    chown -R appuser:appuser /home/appuser

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright
RUN pip install --no-cache-dir playwright

# Change to appuser BEFORE installing browsers
USER appuser
ENV PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright

# Install Playwright browsers with specific architecture handling
RUN if [ "$(uname -m)" = "aarch64" ]; then \
        # ARM64-specific installation
        playwright install chromium; \
    else \
        # x86_64 installation
        playwright install chromium; \
    fi

# Switch back to root to copy files
USER root

# Copy application code
COPY . .

# Fix permissions for application files
RUN chown -R appuser:appuser /app

# Switch back to appuser for running the application
USER appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose the port the app runs on
EXPOSE 8000

# Add health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8000/api/scraper/health || exit 1

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
