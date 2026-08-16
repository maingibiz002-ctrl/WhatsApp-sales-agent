# Official Playwright Python image pre-configured with Chromium & Linux system libraries
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project codebase into container
COPY . .

# Render listens on port 10000 by default
EXPOSE 10000

# Start FastAPI with Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]