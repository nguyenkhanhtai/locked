FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOCKED_HOST=0.0.0.0 \
    LOCKED_PORT=8765 \
    LOCKED_RELOAD=false

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY scripts/ /app/scripts/
COPY pyproject.toml README.md /app/

# Ensure required persistent storage directories exist
RUN mkdir -p /app/backend/db /app/backend/user /app/backend/logs

# Expose web service port
EXPOSE 8765

# Start server
CMD ["python", "backend/run.py"]
