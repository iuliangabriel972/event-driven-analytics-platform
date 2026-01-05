#!/bin/bash
# Automated EC2 deployment script for event platform

set -e

echo "🚀 Deploying Event Platform to EC2..."

# Configuration
INSTANCE_TYPE="t2.micro"
KEY_NAME="your-key-pair"  # Change this
SECURITY_GROUP="sg-xxx"   # Change this
SUBNET_ID="subnet-xxx"    # Change this
REGION="us-east-1"

# Launch EC2 instance
echo "📦 Launching EC2 instance..."
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type $INSTANCE_TYPE \
  --key-name $KEY_NAME \
  --security-group-ids $SECURITY_GROUP \
  --subnet-id $SUBNET_ID \
  --user-data file://ec2-user-data.sh \
  --query 'Instances[0].InstanceId' \
  --output text \
  --region $REGION)

echo "✅ Instance launched: $INSTANCE_ID"

# Wait for instance to be running
echo "⏳ Waiting for instance to be running..."
aws ec2 wait instance-running --instance-ids $INSTANCE_ID --region $REGION

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region $REGION)

echo "✅ Instance is running!"
echo "🌐 Public IP: $PUBLIC_IP"
echo ""
echo "📝 Next steps:"
echo "1. SSH into instance: ssh -i your-key.pem ec2-user@$PUBLIC_IP"
echo "2. Clone repository and start services"
echo "3. Access Producer API: http://$PUBLIC_IP:8000"
echo "4. Access GraphQL API: http://$PUBLIC_IP:8001"

