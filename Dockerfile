# Use official Playwright image which has all browser dependencies pre-installed
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Firefox is used in our automation)
RUN playwright install firefox chromium

# Copy the rest of the application code
COPY . .

# Set Environment Variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=dashboard/app.py
ENV PYTHONPATH=/app

# Expose the dashboard port
EXPOSE 5001

# Command to run the dashboard
CMD ["python", "dashboard/app.py"]
