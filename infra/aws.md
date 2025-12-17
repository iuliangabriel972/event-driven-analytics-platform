# AWS Deployment Guide

This guide covers deploying the event-driven analytics platform to AWS using the Free Tier.

## Prerequisites

1. AWS Account with Free Tier eligibility
2. AWS CLI installed and configured (`aws configure --profile <profile-name>`)
3. Docker and Docker Compose installed
4. Basic understanding of AWS services

## AWS Free Tier Limits

### DynamoDB
- **Storage**: 25 GB
- **Read/Write Capacity**: 25 read units and 25 write units per second
- **Data Transfer**: 1 GB out (free)

### S3
- **Storage**: 5 GB
- **Requests**: 20,000 GET requests, 2,000 PUT requests
- **Data Transfer**: 1 GB out (free)

### EC2 (if needed)
- **Instance**: t2.micro (750 hours/month)
- **Storage**: 30 GB EBS

## Step 1: Create AWS Resources

### 1.1 Create S3 Bucket

```bash
aws s3 mb s3://event-platform-raw-events --region us-east-1 --profile <your-profile>
```

**Note**: S3 bucket names must be globally unique. Adjust the bucket name if needed.

### 1.2 Create DynamoDB Table

The table will be created automatically by the consumer service, but you can pre-create it:

```bash
aws dynamodb create-table \
  --table-name EventsHot \
  --attribute-definitions \
    AttributeName=event_id,AttributeType=S \
    AttributeName=timestamp,AttributeType=S \
    AttributeName=event_type,AttributeType=S \
    AttributeName=user_id,AttributeType=S \
  --key-schema \
    AttributeName=event_id,KeyType=HASH \
    AttributeName=timestamp,KeyType=RANGE \
  --global-secondary-indexes \
    'IndexName=event-type-index,KeySchema=[{AttributeName=event_type,KeyType=HASH},{AttributeName=timestamp,KeyType=RANGE}],Projection={ProjectionType=ALL}' \
    'IndexName=user-id-index,KeySchema=[{AttributeName=user_id,KeyType=HASH},{AttributeName=timestamp,KeyType=RANGE}],Projection={ProjectionType=ALL}' \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1 \
  --profile <your-profile>
```

## Step 2: Configure IAM Permissions

Create an IAM user or use an existing one with the following minimal permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:CreateTable",
        "dynamodb:DescribeTable"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/EventsHot",
        "arn:aws:dynamodb:*:*:table/EventsHot/index/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:CreateBucket",
        "s3:HeadBucket"
      ],
      "Resource": [
        "arn:aws:s3:::event-platform-raw-events",
        "arn:aws:s3:::event-platform-raw-events/*"
      ]
    }
  ]
}
```

## Step 3: Configure Environment Variables

Create a `.env` file (copy from `env.example`):

```bash
cp env.example .env
```

Update the AWS configuration:

```env
AWS_REGION=us-east-1
AWS_PROFILE=your-profile-name
DYNAMODB_TABLE=EventsHot
S3_BUCKET=event-platform-raw-events
```

## Step 4: Deploy Services

### Option A: Deploy to EC2 (Full AWS Deployment)

1. **Launch EC2 Instance**:
   - Use t2.micro (Free Tier eligible)
   - Amazon Linux 2 or Ubuntu
   - Security Group: Allow ports 8000, 8001, 9092

2. **Install Dependencies**:
   ```bash
   sudo yum update -y
   sudo yum install -y docker git
   sudo systemctl start docker
   sudo usermod -a -G docker ec2-user
   ```

3. **Clone and Deploy**:
   ```bash
   git clone <your-repo>
   cd event-platform
   docker-compose up -d
   ```

### Option B: Local Development with AWS Services

Run services locally but connect to AWS DynamoDB and S3:

```bash
docker-compose up -d
```

## Step 5: Verify Deployment

1. **Check Producer API**:
   ```bash
   curl http://localhost:8000/health
   ```

2. **Send Test Event**:
   ```bash
   curl -X POST http://localhost:8000/events \
     -H "Content-Type: application/json" \
     -d '{
       "event_type": "page_view",
       "user_id": "123",
       "payload": {"page": "/home"}
     }'
   ```

3. **Query GraphQL API**:
   ```bash
   curl -X POST http://localhost:8001/graphql \
     -H "Content-Type: application/json" \
     -d '{
       "query": "{ latestEvents(limit: 5) { eventId eventType userId timestamp } }"
     }'
   ```

## Step 6: Monitor and Optimize

### Cost Monitoring

- Use AWS Cost Explorer to monitor Free Tier usage
- Set up billing alerts at 80% of Free Tier limits

### Performance Optimization

1. **DynamoDB**:
   - Monitor read/write capacity
   - Adjust GSI projections if needed
   - Consider TTL for old events

2. **S3**:
   - Enable lifecycle policies for old data
   - Use S3 Intelligent-Tiering (after Free Tier)

3. **Kafka/Redpanda**:
   - Monitor consumer lag
   - Adjust partition count if needed

## Troubleshooting

### Common Issues

1. **AWS Credentials Not Found**:
   - Ensure `~/.aws/credentials` exists
   - Verify profile name matches `AWS_PROFILE`
   - Check IAM permissions

2. **DynamoDB Table Creation Fails**:
   - Verify IAM permissions include `dynamodb:CreateTable`
   - Check table name doesn't conflict
   - Ensure region matches

3. **S3 Bucket Access Denied**:
   - Verify bucket name is correct
   - Check IAM permissions for S3
   - Ensure bucket exists in the specified region

4. **Consumer Not Processing**:
   - Check Kafka/Redpanda connectivity
   - Verify consumer group name
   - Check logs: `docker logs consumer-1`

## Security Best Practices

1. **IAM**: Use least privilege principle
2. **S3**: Enable versioning and encryption
3. **DynamoDB**: Enable encryption at rest
4. **Network**: Use VPC and security groups
5. **Secrets**: Use AWS Secrets Manager for production

## Scaling Beyond Free Tier

When you exceed Free Tier limits:

1. **DynamoDB**: Switch to provisioned capacity
2. **S3**: Use lifecycle policies and Glacier
3. **EC2**: Consider ECS/Fargate for container orchestration
4. **Kafka**: Use AWS MSK (Managed Streaming for Kafka)

## Additional Resources

- [AWS Free Tier](https://aws.amazon.com/free/)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [S3 Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html)

