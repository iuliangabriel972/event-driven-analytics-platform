#!/bin/bash
# Create Kafka infrastructure in AWS
# Option 1: AWS MSK (Managed Kafka) - Recommended
# Option 2: EC2 with Redpanda - Cheaper alternative

set -e

REGION="us-east-1"
VPC_ID=$1
SUBNET_IDS=$2  # Comma-separated subnet IDs

if [ -z "$VPC_ID" ] || [ -z "$SUBNET_IDS" ]; then
    echo "Usage: ./create-kafka.sh <VPC-ID> <SUBNET-IDS>"
    echo "Example: ./create-kafka.sh vpc-12345 subnet-1,subnet-2"
    exit 1
fi

echo "📦 Setting up Kafka infrastructure..."
echo "VPC: $VPC_ID"
echo "Subnets: $SUBNET_IDS"
echo ""

# Option 1: AWS MSK (Recommended for production)
echo "Option 1: AWS MSK (Managed Kafka)"
echo "  Cost: ~$0.10/hour per broker"
echo "  Pros: Fully managed, highly available"
echo ""
echo "To create MSK cluster, use AWS Console or:"
echo "  aws kafka create-cluster --cluster-name event-platform-kafka ..."
echo ""

# Option 2: EC2 with Redpanda (Cheaper)
echo "Option 2: EC2 with Redpanda (Free Tier eligible)"
echo "  Cost: t2.micro (750 hours/month free)"
echo "  Pros: Free tier, simpler setup"
echo ""

read -p "Create EC2 instance with Redpanda? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Create security group for Kafka
    SG_ID=$(aws ec2 create-security-group \
      --group-name event-platform-kafka-sg \
      --description "Security group for Kafka/Redpanda" \
      --vpc-id $VPC_ID \
      --region $REGION \
      --query 'GroupId' \
      --output text)
    
    # Allow Kafka port from ECS security group
    aws ec2 authorize-security-group-ingress \
      --group-id $SG_ID \
      --protocol tcp \
      --port 9092 \
      --cidr 10.0.0.0/16 \
      --region $REGION
    
    # Launch EC2 instance
    INSTANCE_ID=$(aws ec2 run-instances \
      --image-id ami-0c55b159cbfafe1f0 \
      --instance-type t2.micro \
      --subnet-id $(echo $SUBNET_IDS | cut -d',' -f1) \
      --security-group-ids $SG_ID \
      --user-data file://infra/ec2-kafka-user-data.sh \
      --region $REGION \
      --query 'Instances[0].InstanceId' \
      --output text)
    
    echo "✅ EC2 instance created: $INSTANCE_ID"
    echo "⏳ Wait 2-3 minutes for Redpanda to start"
    echo ""
    echo "Get private IP:"
    echo "  aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text"
fi

