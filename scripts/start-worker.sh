#!/bin/bash
# Start LLM Worker in Docker

cd "$(dirname "$0")/../workers/llm-worker"

echo "Building Docker image..."
docker build -t llm-worker:latest .

echo "Starting worker..."
docker run -d \
  --name llm-worker \
  --network host \
  --env-file .env \
  --restart unless-stopped \
  llm-worker:latest

echo "Worker started! Check logs with: docker logs -f llm-worker"
