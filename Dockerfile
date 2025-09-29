FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY app/ ./app/

# Create data directory
RUN mkdir -p /app/data

# Create startup script
RUN echo '#!/bin/bash' > /app/startup.sh && \
    echo 'export PORT=${PORT:-8000}' >> /app/startup.sh && \
    echo 'echo "Starting MDSpecialist API on port $PORT"' >> /app/startup.sh && \
    echo 'exec uvicorn main:app --host 0.0.0.0 --port $PORT' >> /app/startup.sh && \
    chmod +x /app/startup.sh

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD ["sh", "-c", "curl -f http://localhost:${PORT:-8000}/healthz || exit 1"]

# Run the application using startup script
CMD ["./startup.sh"]
