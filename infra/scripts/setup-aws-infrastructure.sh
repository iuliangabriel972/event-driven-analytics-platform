#!/bin/bash
# Setup AWS infrastructure for ECS deployment
# Creates VPC, subnets, security groups, and IAM roles

set -e

REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "🏗️  Setting up AWS infrastructure..."

# Step 1: Create VPC
echo "📦 Creating VPC..."
VPC_ID=$(aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --region $REGION \
  --query 'Vpc.VpcId' \
  --output text)

aws ec2 create-tags --resources $VPC_ID --tags Key=Name,Value=event-platform-vpc --region $REGION
echo "✅ VPC created: $VPC_ID"

# Step 2: Create Internet Gateway
echo "🌐 Creating Internet Gateway..."
IGW_ID=$(aws ec2 create-internet-gateway \
  --region $REGION \
  --query 'InternetGateway.InternetGatewayId' \
  --output text)

aws ec2 attach-internet-gateway \
  --vpc-id $VPC_ID \
  --internet-gateway-id $IGW_ID \
  --region $REGION

echo "✅ Internet Gateway created: $IGW_ID"

# Step 3: Create Subnets
echo "📡 Creating subnets..."
PUBLIC_SUBNET_1=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.1.0/24 \
  --availability-zone ${REGION}a \
  --region $REGION \
  --query 'Subnet.SubnetId' \
  --output text)

PUBLIC_SUBNET_2=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.2.0/24 \
  --availability-zone ${REGION}b \
  --region $REGION \
  --query 'Subnet.SubnetId' \
  --output text)

PRIVATE_SUBNET_1=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.3.0/24 \
  --availability-zone ${REGION}a \
  --region $REGION \
  --query 'Subnet.SubnetId' \
  --output text)

PRIVATE_SUBNET_2=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.4.0/24 \
  --availability-zone ${REGION}b \
  --region $REGION \
  --query 'Subnet.SubnetId' \
  --output text)

echo "✅ Subnets created"
echo "  Public: $PUBLIC_SUBNET_1, $PUBLIC_SUBNET_2"
echo "  Private: $PRIVATE_SUBNET_1, $PRIVATE_SUBNET_2"

# Step 4: Create Route Tables
echo "🛣️  Creating route tables..."
PUBLIC_RT=$(aws ec2 create-route-table \
  --vpc-id $VPC_ID \
  --region $REGION \
  --query 'RouteTable.RouteTableId' \
  --output text)

aws ec2 create-route \
  --route-table-id $PUBLIC_RT \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id $IGW_ID \
  --region $REGION

aws ec2 associate-route-table --subnet-id $PUBLIC_SUBNET_1 --route-table-id $PUBLIC_RT --region $REGION
aws ec2 associate-route-table --subnet-id $PUBLIC_SUBNET_2 --route-table-id $PUBLIC_RT --region $REGION

echo "✅ Route tables configured"

# Step 5: Create Security Groups
echo "🔒 Creating security groups..."

# ALB Security Group
ALB_SG=$(aws ec2 create-security-group \
  --group-name event-platform-alb-sg \
  --description "Security group for ALB" \
  --vpc-id $VPC_ID \
  --region $REGION \
  --query 'GroupId' \
  --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $ALB_SG \
  --protocol tcp \
  --port 8000 \
  --cidr 0.0.0.0/0 \
  --region $REGION

aws ec2 authorize-security-group-ingress \
  --group-id $ALB_SG \
  --protocol tcp \
  --port 8001 \
  --cidr 0.0.0.0/0 \
  --region $REGION

# ECS Security Group
ECS_SG=$(aws ec2 create-security-group \
  --group-name event-platform-ecs-sg \
  --description "Security group for ECS tasks" \
  --vpc-id $VPC_ID \
  --region $REGION \
  --query 'GroupId' \
  --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $ECS_SG \
  --protocol tcp \
  --port 8000 \
  --source-group $ALB_SG \
  --region $REGION

aws ec2 authorize-security-group-ingress \
  --group-id $ECS_SG \
  --protocol tcp \
  --port 8001 \
  --source-group $ALB_SG \
  --region $REGION

echo "✅ Security groups created"
echo "  ALB SG: $ALB_SG"
echo "  ECS SG: $ECS_SG"

# Step 6: Create IAM Roles
echo "👤 Creating IAM roles..."

# Execution Role
aws iam create-role \
  --role-name ecsTaskExecutionRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' 2>/dev/null || echo "Role exists"

aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Task Role
aws iam create-role \
  --role-name ecsTaskRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' 2>/dev/null || echo "Role exists"

aws iam put-role-policy \
  --role-name ecsTaskRole \
  --policy-name EventPlatformPolicy \
  --policy-document file://infra/iam/task-role-policy.json

echo "✅ IAM roles created"

# Step 7: Create CloudWatch Log Groups
echo "📊 Creating CloudWatch log groups..."
aws logs create-log-group --log-group-name /ecs/event-platform-producer --region $REGION 2>/dev/null || echo "Log group exists"
aws logs create-log-group --log-group-name /ecs/event-platform-consumer --region $REGION 2>/dev/null || echo "Log group exists"
aws logs create-log-group --log-group-name /ecs/event-platform-graphql --region $REGION 2>/dev/null || echo "Log group exists"

echo ""
echo "✅ Infrastructure setup complete!"
echo ""
echo "📝 Configuration values to use:"
echo "  VPC ID: $VPC_ID"
echo "  Public Subnets: $PUBLIC_SUBNET_1, $PUBLIC_SUBNET_2"
echo "  Private Subnets: $PRIVATE_SUBNET_1, $PRIVATE_SUBNET_2"
echo "  ALB Security Group: $ALB_SG"
echo "  ECS Security Group: $ECS_SG"
echo ""
echo "Update these values in:"
echo "  - infra/ecs-services/*.json"
echo "  - infra/ecs-task-definitions/*.json (for Kafka endpoint)"

