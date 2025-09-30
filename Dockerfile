FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements_simple.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && \
    pip list | grep fastapi && \
    echo "FastAPI installation verified"

# Copy application code
COPY main_container.py ./main.py
COPY backend/app/ ./app/

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD ["sh", "-c", "curl -f http://localhost:${PORT:-8000}/healthz || exit 1"]

# Debug: Check what's installed
RUN echo "=== Python packages ===" && pip list && echo "=== Python path ===" && python -c "import sys; print(sys.path)" && echo "=== Try importing fastapi ===" && python -c "import fastapi; print('FastAPI imported successfully')"

# Run the application directly with proper shell expansion
CMD ["bash", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
