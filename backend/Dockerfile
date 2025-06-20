FROM python:3.12-slim

# Install system dependencies including GPS processing tools and SIMD optimization libs
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    exiftool \
    libimage-exiftool-perl \
    libheif1 \
    libjpeg-dev \
    zlib1g-dev \
    libtiff5-dev \
    libopenjp2-7-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy backend requirements first for better caching
COPY backend/requirements.txt ./requirements.txt

# Uninstall regular Pillow and install Pillow-SIMD for faster image processing
RUN pip uninstall -y pillow || true && \
    pip install --no-cache-dir --force-reinstall pillow-simd

# Install other Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the photo_core library and install it
COPY libs/photo_core /tmp/photo_core
RUN pip install -e /tmp/photo_core

# Copy backend application code
COPY backend /app

# Create storage directory
RUN mkdir -p /srv/photo-timeline/storage

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 