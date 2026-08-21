FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (e.g. for building some python packages if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set PYTHONPATH so absolute imports work
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run the FastAPI app using Uvicorn
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
