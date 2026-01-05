#!/bin/bash
# User data script for EC2 Kafka/Redpanda instance

yum update -y
yum install -y docker

systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Get private IP BEFORE starting Docker container
PRIVATE_IP=$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4)

# Run Redpanda
docker run -d \
  --name redpanda \
  --restart unless-stopped \
  -p 9092:9092 \
  -p 8081:8081 \
  -p 8082:8082 \
  redpandadata/redpanda:v23.2.11 \
  redpanda start \
  --kafka-addr internal://0.0.0.0:9092 \
  --advertise-kafka-addr internal://$PRIVATE_IP:9092 \
  --smp 1 \
  --memory 1G \
  --mode dev-container

echo "✅ Redpanda started with advertise address: $PRIVATE_IP:9092"

