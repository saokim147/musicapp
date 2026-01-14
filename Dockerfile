FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies
# Install base dependencies from pyproject.toml
RUN uv pip install --system --no-cache . && \
    # Install dev dependencies needed for the app
    uv pip install --system --no-cache \
        torch>=2.9.1 \
        faiss-cpu>=1.13.2 \
        pydub>=0.25.1 \
        scikit-learn>=1.8.0 \
        pydantic-settings>=2.12.0 \
        pandas>=2.3.3 && \
    # Clean up
    rm -rf /root/.cache

# Copy application code
COPY backend/ ./backend/
COPY model/ ./model/
COPY audios/ ./audios/

# Create necessary directories
RUN mkdir -p /app/checkpoints /app/cache /app/preprocessed /app/uploads

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run the application
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
