FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /data/chroma

# Environment variables
ENV PYTHONPATH=/app
ENV CHROMA_PERSIST_DIR=/data/chroma
ENV DB_PATH=/data/prototype.db

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
