FROM python:3.12-slim

# Install system libraries required by OpenCV and ONNXRuntime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set up non-root user permissions for Hugging Face Spaces
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:${PATH}"

WORKDIR /home/user/app

# Copy requirements & install dependencies
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source files
COPY --chown=user . .

# Expose port 7860 for Hugging Face Spaces
EXPOSE 7860

# Run Uvicorn server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7860"]
