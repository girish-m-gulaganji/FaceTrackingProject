FROM python:3.12-slim

# Install system libraries required by OpenCV and ONNXRuntime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements & install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source files
COPY . .

# Expose port 8000
EXPOSE 8000

# Run Uvicorn server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
