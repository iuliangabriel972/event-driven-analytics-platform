#!/bin/bash
# Build Docker images on EC2 instance
# This script runs on the EC2 instance

set -e

REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_BASE="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo "🔐 Logging into ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_BASE

echo "📦 Installing Docker..."
sudo yum update -y
sudo yum install -y docker git
sudo systemctl start docker
sudo usermod -a -G docker ec2-user
sudo systemctl enable docker

echo "🏗️  Building images..."

echo "  Building telemetry-api..."
sudo docker build -f Dockerfile.producer -t ${ECR_BASE}/event-platform-telemetry-api:latest .
sudo docker push ${ECR_BASE}/event-platform-telemetry-api:latest

echo "  Building processor..."
sudo docker build -f Dockerfile.consumer -t ${ECR_BASE}/event-platform-processor:latest .
sudo docker push ${ECR_BASE}/event-platform-processor:latest

echo "  Building analytics-api..."
sudo docker build -f Dockerfile.graphql -t ${ECR_BASE}/event-platform-analytics-api:latest .
sudo docker push ${ECR_BASE}/event-platform-analytics-api:latest

echo "✅ All images built and pushed!"

echo "🔄 Forcing ECS service updates..."
aws ecs update-service --cluster event-platform-cluster --service event-platform-telemetry-api --force-new-deployment --region $REGION
aws ecs update-service --cluster event-platform-cluster --service event-platform-processor --force-new-deployment --region $REGION
aws ecs update-service --cluster event-platform-cluster --service event-platform-analytics-api --force-new-deployment --region $REGION

echo "✅ Done! Services will start with new images."

