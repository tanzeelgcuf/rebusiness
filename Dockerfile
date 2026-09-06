# Multi-Stage Production Dockerfile for RFQ Automation SaaS Platform
# Stage 1: Build dependencies
# Stage 2: Production runtime with non-root user

# ============================================================
# Stage 1: Builder - Install dependencies in isolated layer
# ============================================================
FROM python:3.11-slim AS builder

# Set build-time environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy requirements first for better layer caching
COPY requirements-saas.txt requirements.txt ./

# Install Python dependencies into isolated prefix
RUN pip install --prefix=/install --no-cache-dir -r requirements-saas.txt

# ============================================================
# Stage 2: Runtime - Minimal production image
# ============================================================
FROM python:3.11-slim AS runtime

# Set runtime environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    FLASK_ENV=production \
    PORT=5000 \
    WORKERS=4 \
    TIMEOUT=120

# Install runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libxml2 \
    libxslt1.1 \
    libffi8 \
    libssl3 \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r -g 1000 appuser \
    && useradd -r -u 1000 -g appuser -m -s /bin/bash appuser

# Copy Python dependencies from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . /app

# Create necessary directories with proper ownership
RUN mkdir -p /app/logs /app/uploads /app/instance /app/data \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/api/v1/health || exit 1

# Expose port
EXPOSE 5000

# Use tini as PID 1 for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Production server: gunicorn with optimized workers
# - 4 workers (configurable via WORKERS env var)
# - 2 threads per worker for I/O concurrency
# - 120s timeout for long-running automation tasks
# - Preload app for memory efficiency
# - Access logs to stdout for container log collection
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "4", \
     "--threads", "2", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--keep-alive", "5", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--preload", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info", \
     "run:app"]
