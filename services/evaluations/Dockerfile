FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    build-essential \
    docker.io \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Install optional dependencies for full functionality
RUN pip install --no-cache-dir -e ".[web,code,safety,multimodal]"

# Copy source code
COPY src/ ./src/
COPY configs/ ./configs/
COPY scripts/ ./scripts/

# Set environment variables
ENV PYTHONPATH=/app/src
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Create directories for evaluation results and cache
RUN mkdir -p /app/results /app/cache /app/logs

# Expose port for interactive reports
EXPOSE 8080

# Default command
CMD ["python", "-m", "evaluations.cli", "--help"]