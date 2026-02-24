FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    tesseract-ocr-fra \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp for multimedia agent
RUN pip install --no-cache-dir yt-dlp

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./requirements.txt
COPY backend/requirements-docling.txt ./requirements-docling.txt
RUN pip install --no-cache-dir -r requirements.txt
ARG INSTALL_DOCLING=false
RUN if [ "$INSTALL_DOCLING" = "true" ]; then pip install --no-cache-dir -r requirements-docling.txt; fi

# Copy application code
COPY backend/ .
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini

# Create runtime user for workers and writable temp directories.
RUN groupadd -g 10001 appuser && useradd -m -u 10001 -g 10001 appuser \
    && mkdir -p /tmp/audio /tmp/media \
    && chown -R appuser:appuser /app /tmp/audio /tmp/media

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
