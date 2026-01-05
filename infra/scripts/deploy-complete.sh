#!/bin/bash
# Complete deployment script - Sets up everything in AWS
# Run this after setup-aws-infrastructure.sh

set -e

REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "🚀 Complete AWS Deployment"
echo "============================"
echo ""

# Get infrastructure values
echo "📋 Getting infrastructure details..."
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=tag:Name,Values=event-platform-vpc" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --region $REGION)

PUBLIC_SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=cidr-block,Values=10.0.1.0/24,10.0.2.0/24" \
  --query 'Subnets[*].SubnetId' \
  --output text \
  --region $REGION)

ALB_SG=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=event-platform-alb-sg" \
  --query 'SecurityGroups[0].GroupId' \
  --output text \
  --region $REGION)

ECS_SG=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=event-platform-ecs-sg" \
  --query 'SecurityGroups[0].GroupId' \
  --output text \
  --region $REGION)

echo "VPC: $VPC_ID"
echo "Public Subnets: $PUBLIC_SUBNETS"
echo "ALB Security Group: $ALB_SG"
echo "ECS Security Group: $ECS_SG"
echo ""

# Step 1: Deploy Docker images
echo "📦 Step 1: Building and pushing Docker images..."
./infra/scripts/deploy-to-aws.sh

# Step 2: Create Application Load Balancer
echo ""
echo "⚖️  Step 2: Creating Application Load Balancer..."
SUBNET_ARRAY=($PUBLIC_SUBNETS)
ALB_ARN=$(aws elbv2 create-load-balancer \
  --name event-platform-alb \
  --subnets ${SUBNET_ARRAY[0]} ${SUBNET_ARRAY[1]} \
  --security-groups $ALB_SG \
  --region $REGION \
  --query 'LoadBalancers[0].LoadBalancerArn' \
  --output text)

echo "✅ ALB created: $ALB_ARN"

# Step 3: Create Target Groups
echo ""
echo "🎯 Step 3: Creating target groups..."
PRODUCER_TG_ARN=$(aws elbv2 create-target-group \
  --name event-platform-producer \
  --protocol HTTP \
  --port 8000 \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path /health \
  --region $REGION \
  --query 'TargetGroups[0].TargetGroupArn' \
  --output text)

GRAPHQL_TG_ARN=$(aws elbv2 create-target-group \
  --name event-platform-graphql \
  --protocol HTTP \
  --port 8001 \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path /health \
  --region $REGION \
  --query 'TargetGroups[0].TargetGroupArn' \
  --output text)

echo "✅ Target groups created"

# Step 4: Create Listeners
echo ""
echo "🔊 Step 4: Creating ALB listeners..."
aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTP \
  --port 8000 \
  --default-actions Type=forward,TargetGroupArn=$PRODUCER_TG_ARN \
  --region $REGION

aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTP \
  --port 8001 \
  --default-actions Type=forward,TargetGroupArn=$GRAPHQL_TG_ARN \
  --region $REGION

echo "✅ Listeners created"

# Step 5: Update and register task definitions
echo ""
echo "📝 Step 5: Registering task definitions..."
# Update task definitions with account ID and subnets
sed "s|<ACCOUNT-ID>|$ACCOUNT_ID|g" infra/ecs-task-definitions/producer-task.json | \
  sed "s|<SUBNET-ID-1>|${SUBNET_ARRAY[0]}|g" | \
  sed "s|<SUBNET-ID-2>|${SUBNET_ARRAY[1]}|g" | \
  sed "s|<SECURITY-GROUP-ID>|$ECS_SG|g" | \
  aws ecs register-task-definition --cli-input-json file:///dev/stdin --region $REGION

sed "s|<ACCOUNT-ID>|$ACCOUNT_ID|g" infra/ecs-task-definitions/consumer-task.json | \
  sed "s|<SUBNET-ID-1>|${SUBNET_ARRAY[0]}|g" | \
  sed "s|<SUBNET-ID-2>|${SUBNET_ARRAY[1]}|g" | \
  sed "s|<SECURITY-GROUP-ID>|$ECS_SG|g" | \
  aws ecs register-task-definition --cli-input-json file:///dev/stdin --region $REGION

sed "s|<ACCOUNT-ID>|$ACCOUNT_ID|g" infra/ecs-task-definitions/graphql-task.json | \
  sed "s|<SUBNET-ID-1>|${SUBNET_ARRAY[0]}|g" | \
  sed "s|<SUBNET-ID-2>|${SUBNET_ARRAY[1]}|g" | \
  sed "s|<SECURITY-GROUP-ID>|$ECS_SG|g" | \
  aws ecs register-task-definition --cli-input-json file:///dev/stdin --region $REGION

echo "✅ Task definitions registered"

# Step 6: Create ECS Services
echo ""
echo "🚀 Step 6: Creating ECS services..."
CLUSTER_NAME="event-platform-cluster"

# Update service JSON files
sed "s|<SUBNET-ID-1>|${SUBNET_ARRAY[0]}|g" infra/ecs-services/producer-service.json | \
  sed "s|<SUBNET-ID-2>|${SUBNET_ARRAY[1]}|g" | \
  sed "s|<SECURITY-GROUP-ID>|$ECS_SG|g" | \
  sed "s|<PRODUCER-TARGET-GROUP-ARN>|$PRODUCER_TG_ARN|g" | \
  aws ecs create-service --cluster $CLUSTER_NAME --cli-input-json file:///dev/stdin --region $REGION

sed "s|<SUBNET-ID-1>|${SUBNET_ARRAY[0]}|g" infra/ecs-services/consumer-service.json | \
  sed "s|<SUBNET-ID-2>|${SUBNET_ARRAY[1]}|g" | \
  sed "s|<SECURITY-GROUP-ID>|$ECS_SG|g" | \
  aws ecs create-service --cluster $CLUSTER_NAME --cli-input-json file:///dev/stdin --region $REGION

sed "s|<SUBNET-ID-1>|${SUBNET_ARRAY[0]}|g" infra/ecs-services/graphql-service.json | \
  sed "s|<SUBNET-ID-2>|${SUBNET_ARRAY[1]}|g" | \
  sed "s|<SECURITY-GROUP-ID>|$ECS_SG|g" | \
  sed "s|<GRAPHQL-TARGET-GROUP-ARN>|$GRAPHQL_TG_ARN|g" | \
  aws ecs create-service --cluster $CLUSTER_NAME --cli-input-json file:///dev/stdin --region $REGION

echo "✅ ECS services created"

# Step 7: Configure Auto-Scaling
echo ""
echo "📈 Step 7: Configuring auto-scaling for consumers..."
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/$CLUSTER_NAME/event-platform-consumer \
  --min-capacity 2 \
  --max-capacity 10 \
  --region $REGION

aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/$CLUSTER_NAME/event-platform-consumer \
  --policy-name consumer-cpu-scaling \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file://infra/autoscaling-policy.json \
  --region $REGION

echo "✅ Auto-scaling configured"

# Get ALB DNS
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --load-balancer-arns $ALB_ARN \
  --query 'LoadBalancers[0].DNSName' \
  --output text \
  --region $REGION)

echo ""
echo "✅ Deployment Complete!"
echo ""
echo "🌐 Public URLs:"
echo "  Producer API: http://$ALB_DNS:8000"
echo "  GraphQL API: http://$ALB_DNS:8001"
echo ""
echo "🧪 Test from your local machine:"
echo "  \$env:PRODUCER_API_URL = 'http://$ALB_DNS:8000'"
echo "  .\\test_simple.ps1"
echo ""
echo "📊 Monitor services:"
echo "  aws ecs list-services --cluster $CLUSTER_NAME --region $REGION"
echo "  aws logs tail /ecs/event-platform-producer --follow --region $REGION"

