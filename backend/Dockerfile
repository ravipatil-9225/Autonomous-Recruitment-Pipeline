FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (cache layer)
COPY backend/requirements-backend.txt ./backend/requirements-backend.txt
COPY requirements.txt ./requirements.txt

# Install all dependencies
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r backend/requirements-backend.txt

# Download spaCy English model
RUN python -m spacy download en_core_web_sm

# Copy source code
COPY . .

# Set Python path so `from backend.app...` and `from graph...` both resolve
ENV PYTHONPATH=/app

# Default command: run API server
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
