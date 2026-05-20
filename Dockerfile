FROM python:3.11-slim

# Install minimal baseline tools required to add external repositories
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Add the official Google Chrome GPG key and repository
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Update apt and install Chrome. 
# Installing google-chrome-stable automatically forces apt to resolve and install 
# every underlying graphical library dependency (X11, NSS, Cairo, etc.) cleanly.
RUN apt-get update && apt-get install -y --no-install-recommends \
    google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Set working directory inside the container
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set environment variable to output python prints immediately to console logs
ENV PYTHONUNBUFFERED=1

# Execute the scraper
CMD ["python", "scraper.py"]