# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Install Chrome and ChromeDriver
# Based on https://github.com/GoogleChrome/puppeteer/blob/main/docs/troubleshooting.md#running-puppeteer-on-docker
# And WebDriverManager for Python
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf2.0-0 \
    libgbm1 \
    libgconf-2-4 \
    libgiorp-2.0-0 \
    libglib2.0-0 \
    libglib2.0-dev \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    lsb-release \
    xdg-utils \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Add Google Chrome stable
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update && apt-get install -y google-chrome-stable

# Install Java (needed by openpyxl for some functionalities, and potentially webdriver-manager)
# openpyxl does not strictly require Java, but some spreadsheet processing libraries might.
# For simplicity, keeping it here for now. If issues arise, it can be removed.
RUN apt-get update && apt-get install -y default-jdk

# Copy local requirements file and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Ensure chromedriver is available in PATH
# WebDriverManager will handle downloading the correct version, but it needs to be executable
# The system-installed chrome is at /usr/bin/google-chrome
# WebDriverManager will try to put chromedriver in /usr/local/bin or similar, which is in PATH
ENV PATH="/usr/bin:${PATH}"

# Command to run the application (your main workflow script)
CMD ["python", "main_workflow.py"]
