FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker code
COPY llm_worker.py .

# Run worker
CMD ["python", "llm_worker.py"]
