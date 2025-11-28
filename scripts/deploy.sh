#!/bin/bash
# Deploy Camunda process to running instance

CAMUNDA_URL="http://192.168.13.52:8080/engine-rest"
BPMN_FILE="../bpmn/ticket-refund-process.bpmn"

echo "Deploying process to Camunda..."

curl -X POST "${CAMUNDA_URL}/deployment/create" \
  -H "Content-Type: multipart/form-data" \
  -F "deployment-name=ticket-refund" \
  -F "deploy-changed-only=true" \
  -F "deployment-source=local" \
  -F "data=@${BPMN_FILE}"

echo ""
echo "Deployment complete!"
