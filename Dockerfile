FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create data directories so the app starts cleanly
RUN mkdir -p data/logs data/faiss_index data/experiments data/papers \
             data/reports data/memory data/twin_papers

# Expose FastAPI and Gradio ports
EXPOSE 8000 7860

# Default: serve FastAPI (Render overrides this per service)
CMD ["python", "main.py", "--serve"]
