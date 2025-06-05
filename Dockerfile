# Multi-stage Dockerfile for Semantic Kernel Demo with LLM Evaluation
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set work directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Development stage
FROM base as development

# Install additional development dependencies
RUN pip install \
    pytest-xdist \
    pytest-benchmark \
    pytest-timeout \
    jupyter \
    ipykernel

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs test-reports htmlcov && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Default command for development
CMD ["python", "basic_agent.py"]

# Test stage - optimized for CI/CD
FROM base as test

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs test-reports htmlcov && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Default command for running tests
CMD ["pytest", "-v", "--cov=.", "--cov-report=html", "--cov-report=xml", "--junitxml=test-results.xml"]

# Production stage
FROM base as production

# Copy only necessary application files
COPY config.py .
COPY logging_config.py .
COPY basic_agent.py .
COPY basic_agent_ollama.py .
COPY env.example .
COPY pytest.ini .
COPY pyproject.toml .

# Create necessary directories
RUN mkdir -p logs test-reports && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from config import app_config; print('Health check passed')" || exit 1

# Default command for production
CMD ["python", "basic_agent.py"]

# CI stage - specialized for continuous integration
FROM test as ci

# Install additional CI tools
USER root
RUN pip install \
    sonar-scanner \
    pytest-json-report

# Copy CI specific configurations
COPY sonar-project.properties .
COPY .github/ .github/

# Switch back to non-root user
USER appuser

# Default command for CI
CMD ["make", "ci-test"] 