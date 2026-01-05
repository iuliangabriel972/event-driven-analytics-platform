#!/bin/bash
# Complete AWS deployment script for event platform
# Deploys all services to ECS Fargate

set -e

# Configuration
REGION="us-east-1"
CLUSTER_NAME="event-platform-cluster"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_BASE="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo "🚀 Deploying Event Platform to AWS ECS"
echo "Account ID: $ACCOUNT_ID"
echo "Region: $REGION"
echo ""

# Step 1: Create ECR Repositories
echo "📦 Creating ECR repositories..."
aws ecr create-repository --repository-name event-platform-producer --region $REGION 2>/dev/null || echo "Repository exists"
aws ecr create-repository --repository-name event-platform-consumer --region $REGION 2>/dev/null || echo "Repository exists"
aws ecr create-repository --repository-name event-platform-graphql --region $REGION 2>/dev/null || echo "Repository exists"

# Step 2: Login to ECR
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_BASE

# Step 3: Build and Push Images
echo "🏗️  Building and pushing Docker images..."

# Producer
echo "  Building producer..."
docker build -f Dockerfile.producer -t event-platform-producer:latest .
docker tag event-platform-producer:latest $ECR_BASE/event-platform-producer:latest
docker push $ECR_BASE/event-platform-producer:latest

# Consumer
echo "  Building consumer..."
docker build -f Dockerfile.consumer -t event-platform-consumer:latest .
docker tag event-platform-consumer:latest $ECR_BASE/event-platform-consumer:latest
docker push $ECR_BASE/event-platform-consumer:latest

# GraphQL
echo "  Building graphql..."
docker build -f Dockerfile.graphql -t event-platform-graphql:latest .
docker tag event-platform-graphql:latest $ECR_BASE/event-platform-graphql:latest
docker push $ECR_BASE/event-platform-graphql:latest

# Step 4: Create ECS Cluster
echo "🏗️  Creating ECS cluster..."
aws ecs create-cluster --cluster-name $CLUSTER_NAME --region $REGION 2>/dev/null || echo "Cluster exists"

# Step 5: Register Task Definitions
echo "📝 Registering task definitions..."
# Update image URIs in task definitions
sed "s|<ACCOUNT-ID>|$ACCOUNT_ID|g" infra/ecs-task-definitions/producer-task.json | \
  aws ecs register-task-definition --cli-input-json file:///dev/stdin --region $REGION

sed "s|<ACCOUNT-ID>|$ACCOUNT_ID|g" infra/ecs-task-definitions/consumer-task.json | \
  aws ecs register-task-definition --cli-input-json file:///dev/stdin --region $REGION

sed "s|<ACCOUNT-ID>|$ACCOUNT_ID|g" infra/ecs-task-definitions/graphql-task.json | \
  aws ecs register-task-definition --cli-input-json file:///dev/stdin --region $REGION

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📝 Next steps:"
echo "1. Create VPC, subnets, and security groups"
echo "2. Create Application Load Balancer"
echo "3. Create ECS services using infra/ecs-services/*.json"
echo "4. Configure auto-scaling for consumers"
echo ""
echo "See AWS_DEPLOY_ECS.md for detailed instructions"

