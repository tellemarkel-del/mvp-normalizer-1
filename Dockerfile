FROM python:3.13-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Work directory
WORKDIR /app

# Copy project
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose port for Railway
EXPOSE 5000

# Start Flask app
CMD ["python", "main.py"]
