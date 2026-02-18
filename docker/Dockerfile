FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir flask==2.3.0 requests==2.31.0

# Copy application files (context is docker/ directory)
COPY dca_telegram_handler.py /app/
COPY dca_webhook.py /app/

# Create user_data directory symlink location
RUN mkdir -p /freqtrade/user_data

EXPOSE 5555

CMD ["python", "dca_webhook.py"]
