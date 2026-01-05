#!/bin/bash
# EC2 user data script to install Docker and dependencies

yum update -y
yum install -y docker git

# Start Docker
systemctl start docker
systemctl enable docker

# Add ec2-user to docker group
usermod -a -G docker ec2-user

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install Python and pip (for test script)
yum install -y python3 python3-pip

# Configure AWS credentials (if needed)
# mkdir -p /home/ec2-user/.aws
# Copy credentials file or use IAM role

echo "✅ Docker and dependencies installed"

