# ========================================
# INTELLI-CREDIT Backend — Production Dockerfile
# Deploy to Hugging Face Spaces
# ========================================
FROM python:3.11-slim

# System dependencies for ML + PDF parsing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set up a new user named "user" with user ID 1000
RUN useradd -m -u 1000 user

# Switch to the "user" user
USER user

# Set home to the user's home directory
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Set the working directory to the user's home directory
WORKDIR $HOME/app

# Copy the requirements file into the container at $HOME/app setting the owner to the user
COPY --chown=user requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend code into the app directory
COPY --chown=user . /home/user/app/

# Expose the default port for Hugging Face Spaces
EXPOSE 7860

# Add the current directory to PYTHONPATH so Python can find local modules like 'middleware'
ENV PYTHONPATH="${HOME}/app:${PYTHONPATH}"

# Simple health check endpoint for pinger
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:7860/ping')" || exit 1

# Start FastAPI with uvicorn on port 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
