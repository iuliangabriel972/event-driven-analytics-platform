# Event-Driven Analytics Platform

A scalable, production-ready event-driven analytics platform built with Python, Kafka (Redpanda), GraphQL, and AWS. The platform ingests events via HTTP, streams them through Kafka, processes with scalable consumers, stores data in DynamoDB (hot) and S3 (cold), and exposes read-only data via GraphQL API.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│   Client    │────▶│  Telemetry   │────▶│    Kafka    │────▶│   Processor  │
│             │     │     API      │     │  (Redpanda) │     │  (Consumer) │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
                                                                    │
                                                                    ▼
                                                          ┌──────────────┐
                                                          │  DynamoDB    │
                                                          │  (Hot Data)  │
                                                          └──────────────┘
                                                                    │
                                                                    ▼
                                                          ┌──────────────┐
                                                          │     S3       │
                                                          │ (Cold Data)  │
                                                          └──────────────┘
                                                                    │
                                                                    ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │◀────│   Analytics  │◀────│  DynamoDB   │
│             │     │  GraphQL API │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
```

## Components

### Services

1. **Telemetry API** (Producer)
   - FastAPI service for event ingestion
   - JWT authentication
   - Publishes events to Kafka
   - Prometheus metrics

2. **Processor** (Consumer)
   - Kafka consumer for event processing
   - Writes to DynamoDB (hot storage)
   - Writes to S3 (cold storage)
   - Dead Letter Queue (DLQ) support
   - Prometheus metrics

3. **Analytics API** (GraphQL)
   - Strawberry GraphQL API
   - Read-only queries from DynamoDB
   - JWT authentication
   - Prometheus metrics

4. **Kafka** (Redpanda)
   - Event streaming broker
   - Runs on EC2 instance
   - Kafka-compatible API

5. **Monitoring**
   - Prometheus for metrics collection
   - Grafana for visualization

## Technology Stack

- **Python 3.11**
- **FastAPI** - HTTP services
- **Strawberry GraphQL** - GraphQL API
- **aiokafka** - Async Kafka client
- **Redpanda** - Kafka-compatible broker
- **DynamoDB** - Hot data storage
- **S3** - Cold data storage
- **AWS ECS Fargate** - Container orchestration
- **AWS ALB** - Load balancing
- **Prometheus** - Metrics
- **Grafana** - Dashboards
- **JWT** - Authentication

## Prerequisites

- AWS Account with CLI configured
- Docker Desktop (for building images)
- Python 3.11+
- PowerShell (for scripts)

## AWS Infrastructure

### Resources Created

- **VPC** with public subnets
- **ECS Cluster** (`event-platform-cluster`)
- **ECR Repositories**:
  - `event-platform-telemetry-api`
  - `event-platform-processor`
  - `event-platform-analytics-api`
  - `event-platform-prometheus`
- **DynamoDB Table**: `EventsHot`
- **S3 Bucket**: `event-platform-raw-events`
- **EC2 Instance**: Kafka/Redpanda
- **Application Load Balancer**
- **CloudWatch Log Groups**
- **IAM Roles**: `ecsTaskExecutionRole`, `ecsTaskRole`

### Network Configuration

- Services run in public subnets with public IPs enabled
- Security groups allow:
  - Port 8000 (Telemetry API)
  - Port 8001 (Analytics API)
  - Port 9092 (Kafka)
  - Port 9090 (Prometheus)
  - Port 3000 (Grafana)

## Deployment

### 1. Build and Push Docker Images

```powershell
# Login to ECR
$accountId = "YOUR_ACCOUNT_ID"
$region = "us-east-1"
$registry = "${accountId}.dkr.ecr.${region}.amazonaws.com"
aws ecr get-login-password --region $region | docker login --username AWS --password-stdin $registry

# Build and push images
docker build -f Dockerfile.producer -t "${registry}/event-platform-telemetry-api:latest" .
docker push "${registry}/event-platform-telemetry-api:latest"

docker build -f Dockerfile.consumer -t "${registry}/event-platform-processor:latest" .
docker push "${registry}/event-platform-processor:latest"

docker build -f Dockerfile.graphql -t "${registry}/event-platform-analytics-api:latest" .
docker push "${registry}/event-platform-analytics-api:latest"
```

### 2. Deploy Infrastructure

The infrastructure is deployed via AWS CLI. Key files:
- `infra/ecs-task-definitions/*.json` - ECS task definitions
- `infra/ecs-services/*.json` - ECS service definitions
- `infra/scripts/setup-aws-infrastructure.sh` - Infrastructure setup

### 3. Deploy Services

```powershell
# Register task definitions
aws ecs register-task-definition --cli-input-json file://infra/ecs-task-definitions/telemetry-api-task.json --region us-east-1
aws ecs register-task-definition --cli-input-json file://infra/ecs-task-definitions/processor-task.json --region us-east-1
aws ecs register-task-definition --cli-input-json file://infra/ecs-task-definitions/analytics-api-task.json --region us-east-1

# Create/update services
aws ecs create-service --cli-input-json file://infra/ecs-services/telemetry-api-service.json --region us-east-1
aws ecs create-service --cli-input-json file://infra/ecs-services/processor-service.json --region us-east-1
aws ecs create-service --cli-input-json file://infra/ecs-services/analytics-api-service.json --region us-east-1
```

## Testing

### 1. Generate JWT Token

```powershell
.\scripts\generate_jwt_token.ps1
```

Or manually:

```powershell
python -c "import jwt; from datetime import datetime, timedelta, timezone; payload = {'sub': 'test-user', 'aud': 'event-platform', 'iat': int(datetime.now(timezone.utc).timestamp()), 'exp': int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())}; print(jwt.encode(payload, 'change-me-in-production-use-secrets-manager', algorithm='HS256'))"
```

### 2. Get ALB DNS

```powershell
aws elbv2 describe-load-balancers --region us-east-1 --query 'LoadBalancers[?contains(LoadBalancerName, `event-platform`)].DNSName' --output text
```

### 3. Send Test Events

```powershell
$albDns = "YOUR_ALB_DNS"
$token = "YOUR_JWT_TOKEN"

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

$event = @{
    event_type = "vehicle.location"
    user_id = "user-001"
    payload = @{
        latitude = 40.7128
        longitude = -74.0060
        speed = 60
    }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri "http://${albDns}:8000/events" -Method Post -Headers $headers -Body $event
```

Or use the script:

```powershell
.\scripts\generate_events.ps1 -Count 10 -Interval 2 -JwtToken "YOUR_TOKEN" -ApiUrl "http://YOUR_ALB_DNS:8000"
```

### 4. Query GraphQL API

```powershell
$albDns = "YOUR_ALB_DNS"
$token = "YOUR_JWT_TOKEN"

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

# Latest events
$query = @{
    query = "query { latestEvents(limit: 10) { eventId eventType userId timestamp payload } }"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://${albDns}:8001/graphql" -Method Post -Headers $headers -Body $query

# Events by type
$query = @{
    query = "query { eventsByType(eventType: `"vehicle.location`") { eventId userId timestamp } }"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://${albDns}:8001/graphql" -Method Post -Headers $headers -Body $query

# Events by user
$query = @{
    query = "query { eventsByUser(userId: `"user-001`") { eventId eventType timestamp } }"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://${albDns}:8001/graphql" -Method Post -Headers $headers -Body $query
```

Or use the script:

```powershell
.\scripts\query_graphql.ps1 -Query "query { latestEvents(limit: 10) { eventId eventType userId } }" -JwtToken "YOUR_TOKEN" -ApiUrl "http://YOUR_ALB_DNS:8001"
```

### 5. Verify Data in DynamoDB

```powershell
aws dynamodb scan --table-name EventsHot --region us-east-1 --max-items 10
```

### 6. Check Service Status

```powershell
aws ecs describe-services --cluster event-platform-cluster --services event-platform-telemetry-api event-platform-processor event-platform-analytics-api --region us-east-1 --query 'services[*].[serviceName,runningCount,desiredCount]' --output table
```

## GraphQL Queries

### Available Queries

1. **latestEvents(limit: Int)**
   - Returns the most recent events
   - Example: `query { latestEvents(limit: 10) { eventId eventType userId timestamp payload } }`

2. **eventsByType(eventType: String)**
   - Returns events filtered by type
   - Example: `query { eventsByType(eventType: "vehicle.location") { eventId userId timestamp } }`

3. **eventsByUser(userId: String)**
   - Returns events filtered by user
   - Example: `query { eventsByUser(userId: "user-001") { eventId eventType timestamp } }`

## Monitoring

### Prometheus

- Metrics endpoint: `http://ALB_DNS:9090`
- Scrapes metrics from:
  - Telemetry API: `/metrics` on port 8000
  - Processor: `/metrics` on port 8002
  - Analytics API: `/metrics` on port 8001

### Grafana

- Dashboard: `http://ALB_DNS:3000`
- Default credentials: `admin` / `admin`
- Prometheus data source configured automatically

### Metrics Available

- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency
- `consumer_messages_processed_total` - Messages processed
- `consumer_message_processing_seconds` - Processing time

## Configuration

### Environment Variables

#### Telemetry API
- `KAFKA_BOOTSTRAP_SERVERS` - Kafka broker address (e.g., `10.0.1.204:9092`)
- `KAFKA_TOPIC` - Kafka topic name (default: `events.raw`)
- `JWT_SECRET_KEY` - JWT secret key
- `JWT_ALGORITHM` - JWT algorithm (default: `HS256`)
- `JWT_AUDIENCE` - JWT audience (default: `event-platform`)
- `ENVIRONMENT` - Environment name (default: `production`)

#### Processor
- `KAFKA_BOOTSTRAP_SERVERS` - Kafka broker address
- `KAFKA_TOPIC` - Kafka topic name (default: `events.raw`)
- `KAFKA_DLQ_TOPIC` - Dead letter queue topic (default: `events.dlq`)
- `KAFKA_CONSUMER_GROUP` - Consumer group ID (default: `event-processors`)
- `DYNAMODB_TABLE` - DynamoDB table name (default: `EventsHot`)
- `S3_BUCKET` - S3 bucket name (default: `event-platform-raw-events`)
- `AWS_REGION` - AWS region (default: `us-east-1`)
- `METRICS_PORT` - Prometheus metrics port (default: `8002`)

#### Analytics API
- `DYNAMODB_TABLE` - DynamoDB table name (default: `EventsHot`)
- `AWS_REGION` - AWS region (default: `us-east-1`)
- `JWT_SECRET_KEY` - JWT secret key
- `JWT_ALGORITHM` - JWT algorithm (default: `HS256`)
- `JWT_AUDIENCE` - JWT audience (default: `event-platform`)

## Project Structure

```
event-driven-analytics-platform/
├── producer/              # Telemetry API service
│   ├── main.py           # FastAPI application
│   ├── kafka.py          # Kafka producer client
│   └── schemas.py        # Pydantic models
├── consumer/             # Processor service
│   ├── main.py           # Kafka consumer
│   ├── dynamodb.py       # DynamoDB writer
│   ├── s3.py             # S3 writer
│   └── models.py         # Data models
├── graphql_api/          # Analytics API service
│   ├── main.py           # FastAPI + GraphQL
│   └── schema.py         # GraphQL schema
├── shared/               # Shared utilities
│   ├── auth.py           # JWT authentication
│   └── logger.py         # Logging configuration
├── scripts/              # Testing scripts
│   ├── generate_jwt_token.ps1
│   ├── generate_events.ps1
│   └── query_graphql.ps1
├── infra/                # Infrastructure as Code
│   ├── ecs-task-definitions/
│   ├── ecs-services/
│   ├── monitoring/
│   └── scripts/
├── Dockerfile.producer    # Telemetry API image
├── Dockerfile.consumer    # Processor image
├── Dockerfile.graphql     # Analytics API image
├── docker-compose.yml    # Local development
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Local Development

### Running with Docker Compose

```bash
docker-compose up -d
```

Services will be available at:
- Telemetry API: `http://localhost:8000`
- Analytics API: `http://localhost:8001`
- Kafka: `localhost:9092`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

### Running Services Locally

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export DYNAMODB_TABLE=EventsHot
export AWS_REGION=us-east-1
```

3. Run services:
```bash
# Producer
python -m producer.main

# Consumer
python -m consumer.main

# GraphQL API
python -m graphql_api.main
```

## Security Notes

⚠️ **Important**: The default JWT secret key (`change-me-in-production-use-secrets-manager`) is for development only. In production:

1. Use AWS Secrets Manager for JWT secrets
2. Rotate keys regularly
3. Use strong, randomly generated keys
4. Enable HTTPS/TLS for all APIs
5. Implement rate limiting
6. Use VPC endpoints for AWS services (to avoid public IPs)

## Troubleshooting

### Services Not Starting

1. Check ECS service logs:
```powershell
aws logs tail /ecs/event-platform-telemetry-api --region us-east-1 --since 10m
```

2. Verify images exist in ECR:
```powershell
aws ecr describe-images --repository-name event-platform-telemetry-api --region us-east-1
```

3. Check task status:
```powershell
aws ecs list-tasks --cluster event-platform-cluster --service-name event-platform-telemetry-api --region us-east-1
```

### Kafka Connection Issues

1. Verify Kafka EC2 instance is running:
```powershell
aws ec2 describe-instances --filters "Name=tag:Name,Values=kafka-redpanda" --region us-east-1
```

2. Check security group rules allow port 9092
3. Verify Kafka IP in task definition environment variables

### Authentication Errors

1. Verify JWT token is valid and not expired
2. Check JWT secret key matches in all services
3. Ensure `audience` claim matches `JWT_AUDIENCE` environment variable

## Cost Optimization

- Use ECS Fargate Spot for non-critical workloads
- Enable DynamoDB on-demand billing
- Use S3 Intelligent-Tiering for cold storage
- Set up auto-scaling based on metrics
- Use CloudWatch Logs retention policies

## License

This project is provided as-is for demonstration purposes.

## Support

For issues or questions, check:
- AWS CloudWatch Logs for service errors
- ECS service events for deployment issues
- Prometheus metrics for performance issues
