# ========================================
# INTELLI-CREDIT Backend — Production Dockerfile
# Deploy to Railway
# ========================================
FROM python:3.11-slim

# System dependencies for ML + PDF parsing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Railway sets PORT env var)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

# Start FastAPI with uvicorn
# Railway sets PORT env var — shell form ensures variable expansion
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
