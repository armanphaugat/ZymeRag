# Use Python 3.12 base image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install full system dependencies for OpenCV, PaddleOCR, Tesseract, and FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    build-essential \
    g++ \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install full multi-modal dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=600 -r requirements.txt

# Copy application source code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT=8000

# Expose server port
EXPOSE 8000

# Run FastAPI backend with Uvicorn
CMD ["uvicorn", "Backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
