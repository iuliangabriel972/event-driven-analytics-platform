# Monitoring Infrastructure Documentation

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [AWS Infrastructure](#aws-infrastructure)
5. [Dynamic Service Discovery](#dynamic-service-discovery)
6. [Security Configuration](#security-configuration)
7. [Deployment Process](#deployment-process)
8. [Access and Usage](#access-and-usage)
9. [Troubleshooting](#troubleshooting)

## Overview

This document details the complete monitoring infrastructure implementation for the event-driven analytics platform. The system uses **Prometheus** for metrics collection and **Grafana** for visualization, both deployed on AWS ECS Fargate.

### Key Design Decisions

1. **Prometheus over CloudWatch**: Provides application-level metrics, custom instrumentation, and better cost control
2. **ECS Fargate**: Serverless container orchestration eliminates server management overhead
3. **Dynamic Service Discovery**: Automatically adapts to changing task IPs when services restart
4. **Internal ALB for Prometheus**: Ensures stable connectivity from Grafana regardless of Prometheus task restarts
5. **FastAPI Instrumentation**: Uses `prometheus_fastapi_instrumentator` for automatic HTTP metrics

## Architecture

```
┌─────────────┐
│   Grafana   │ (Port 3000)
│  Dashboard  │
└──────┬──────┘
       │ Queries metrics via Internal ALB
       │
┌──────▼──────────────────────────┐
│  Internal ALB                   │
│  prometheus-internal            │
│  Port 9090                      │
└──────┬──────────────────────────┘
       │ Routes to Prometheus task
       │
┌──────▼──────────────────────────┐
│  Prometheus                     │
│  - Scrapes metrics every 15s    │
│  - Auto-updates target IPs      │
│  - Stores time-series data      │
└──────┬──────────────────────────┘
       │ Scrapes /metrics endpoints
       │
       ├─────────────┬─────────────┐
       │             │             │
┌──────▼──────┐ ┌───▼────────┐ ┌──▼────────────┐
│ Telemetry   │ │ Analytics  │ │   Processor   │
│    API      │ │    API     │ │   (Future)    │
│  Port 8000  │ │ Port 8001  │ │  Port 8002    │
└─────────────┘ └────────────┘ └───────────────┘
```

## Components

### 1. Prometheus

**Purpose**: Time-series database and metrics collection system

**Version**: 2.51.2

**Docker Image**: Custom image based on `prom/prometheus:v2.51.2`

**Key Features**:
- **Scrape Interval**: 15 seconds
- **Retention**: 15 days (default)
- **Storage**: Ephemeral (task restarts lose historical data)
- **Dynamic Configuration**: Updates target IPs automatically every 60 seconds

**Instrumented Metrics**:

#### Telemetry API (`telemetry-api`)
- `http_requests_total`: Total HTTP requests by method, endpoint, status
- `http_request_duration_seconds`: Request latency histogram
- `kafka_messages_sent_total`: Kafka messages sent by status
- `kafka_send_duration_seconds`: Kafka send operation duration

#### Analytics API (`analytics-api`)
- `http_requests_total`: GraphQL endpoint requests
- `http_request_duration_seconds`: Query execution time
- `dynamodb_operations_total`: DynamoDB operations by operation type, status
- `dynamodb_operation_seconds`: DynamoDB operation duration
- `s3_uploads_total`: S3 upload operations by status
- `s3_upload_seconds`: S3 upload duration

#### System Metrics (all services)
- `up`: Service availability (1 = up, 0 = down)
- `process_cpu_seconds_total`: CPU time consumed
- `process_resident_memory_bytes`: Memory usage

### 2. Grafana

**Purpose**: Metrics visualization and dashboards

**Version**: Latest (via Docker Hub)

**Docker Image**: `grafana/grafana:latest`

**Default Credentials**:
- Username: `admin`
- Password: `admin` (must change on first login)

**Pre-configured Dashboard**: 14 panels covering:
- Service availability
- Request rates and latency
- Kafka throughput
- DynamoDB operations
- S3 uploads
- Error rates
- Resource usage

## AWS Infrastructure

### ECS Cluster

**Name**: `event-platform-cluster`

**Services Running**:
- `event-platform-telemetry-api` (1 task)
- `event-platform-analytics-api` (1 task)
- `event-platform-processor` (1 task)
- `event-platform-prometheus` (1 task)
- `event-platform-grafana` (1 task)

### VPC Configuration

**VPC ID**: `vpc-0b86c758b8a0f14eb`

**Subnets**:
- Public Subnet 1: `subnet-0322341a6fc93eee8` (us-east-1a)
- Public Subnet 2: `subnet-06fdadd8df2bdfeff` (us-east-1b)

**Note**: All ECS tasks have public IPs enabled for internet connectivity (ECR image pulls, AWS API calls)

### Load Balancers

#### 1. Public Application Load Balancer

**Name**: `event-platform-alb`

**DNS**: `event-platform-alb-95530675.us-east-1.elb.amazonaws.com`

**Listeners**:
- Port 8000 → `event-platform-telemetry-api` target group
- Port 8001 → `event-platform-analytics-api` target group
- Port 3000 → `event-platform-grafana` target group
- Port 9090 → `event-platform-prometheus-tg` target group (public Prometheus access)

**Purpose**: External access to services

#### 2. Internal Application Load Balancer

**Name**: `prometheus-internal`

**DNS**: `internal-prometheus-internal-300523112.us-east-1.elb.amazonaws.com`

**Listeners**:
- Port 9090 → `prom-int-tg` target group

**Purpose**: Stable internal endpoint for Grafana to access Prometheus

**Why Internal ALB?**
- Grafana needs a stable endpoint to connect to Prometheus
- Prometheus task IPs change on restart
- Internal ALB provides DNS-based service discovery
- No exposure to public internet (security best practice)

### Security Groups

#### ECS Tasks Security Group

**ID**: `sg-0360789235f0ebb9a`

**Inbound Rules**:
- Port 3000 (TCP) from ALB security group → Grafana
- Port 8000 (TCP) from ALB security group → Telemetry API
- Port 8001 (TCP) from ALB security group → Analytics API
- Port 9090 (TCP) from ALB security group → Prometheus
- All traffic from itself (self-referencing) → Inter-task communication

**Outbound Rules**:
- All traffic to 0.0.0.0/0 → Internet access for AWS API calls

**Why Self-Referencing Rule?**
Allows Prometheus to scrape metrics from API services directly using their internal IPs without going through the ALB.

#### ALB Security Group

**ID**: `sg-0f1e9a13fe693f386`

**Inbound Rules**:
- Port 3000 (TCP) from 0.0.0.0/0 → Public Grafana access
- Port 8000 (TCP) from 0.0.0.0/0 → Public Telemetry API
- Port 8001 (TCP) from 0.0.0.0/0 → Public Analytics API
- Port 9090 (TCP) from 0.0.0.0/0 → Public Prometheus access

**Outbound Rules**:
- All traffic to ECS security group

## Dynamic Service Discovery

### The Problem

ECS Fargate tasks receive dynamic private IPs that change when:
- Tasks are restarted
- Services are updated
- Tasks are replaced due to health check failures

Hardcoding IPs in Prometheus configuration causes monitoring to break after any service restart.

### Solutions Considered

#### 1. ❌ Static IPs in Configuration
**Tried**: Initial implementation with hardcoded IPs
**Failed**: Broke every time services restarted

#### 2. ❌ ALB DNS Names
**Tried**: Configured Prometheus to scrape through public ALB
**Failed**: ALB returns HTML error pages (502 Bad Gateway) instead of metrics

#### 3. ❌ File-Based Service Discovery
**Tried**: Python script updating JSON target files every 60s
**Failed**: Race conditions causing "unexpected end of JSON input" errors

#### 4. ❌ Native ECS Service Discovery
**Tried**: Prometheus `ec2_sd_configs` and custom `ecs_sd_configs`
**Failed**: Prometheus v2.51.2 doesn't support ECS service discovery natively

#### 5. ✅ **Dynamic Configuration Updates (Current Solution)**

**Implementation**: Background shell script that:
1. Queries AWS ECS API for current task IPs
2. Generates new Prometheus config with updated IPs
3. Triggers Prometheus config reload via HTTP API
4. Runs continuously with 60-second intervals

### Implementation Details

**File**: `infra/monitoring/update-prometheus-targets.sh`

**Process**:
```bash
1. Get current task IPs from ECS API
   ↓
2. Compare with previous IPs
   ↓
3. If changed:
   a. Write new /etc/prometheus/prometheus.yml
   b. POST to http://localhost:9090/-/reload
   c. Log the change
   ↓
4. Sleep 60 seconds
   ↓
5. Repeat
```

**Key Features**:
- Zero-downtime reloads (Prometheus `--web.enable-lifecycle` flag)
- Automatic recovery if AWS API temporarily fails
- Logs all IP changes for debugging
- Minimal resource usage (shell script + AWS CLI)

**Why 60 seconds?**
- Balance between responsiveness and API rate limits
- ECS task startup takes 30-60 seconds anyway
- Reduces CloudWatch API costs

## Security Configuration

### IAM Roles

#### 1. ECS Task Execution Role

**ARN**: `arn:aws:iam::410772457866:role/ecsTaskExecutionRole`

**Purpose**: Allows ECS to pull Docker images and write logs

**Managed Policies**:
- `AmazonECSTaskExecutionRolePolicy`

**Required For**:
- Pulling images from ECR
- Writing logs to CloudWatch Logs
- Retrieving secrets (if used)

#### 2. ECS Task Role

**ARN**: `arn:aws:iam::410772457866:role/ecsTaskRole`

**Purpose**: Grants runtime permissions to tasks

**Custom Policy - ECS Read Access**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:ListTasks",
        "ecs:DescribeTasks",
        "ecs:DescribeServices",
        "ecs:DescribeTaskDefinition"
      ],
      "Resource": "*"
    }
  ]
}
```

**Why These Permissions?**
- `ecs:ListTasks`: Find running tasks for a service
- `ecs:DescribeTasks`: Get task details including IP addresses
- Required by `update-prometheus-targets.sh` for dynamic discovery

**Security Best Practice**: Read-only permissions, no write access

### CloudWatch Logs

**Log Groups**:
- `/ecs/event-platform-telemetry-api`
- `/ecs/event-platform-analytics-api`
- `/ecs/event-platform-processor`
- `/ecs/event-platform-prometheus`
- `/ecs/event-platform-grafana`

**Retention**: Not set (indefinite)

**Access**: Via IAM policies attached to task execution role

## Deployment Process

### Docker Images

All images stored in **Amazon ECR**:

**Repository Region**: `us-east-1`

**Images**:
1. `410772457866.dkr.ecr.us-east-1.amazonaws.com/event-platform-telemetry-api:latest`
2. `410772457866.dkr.ecr.us-east-1.amazonaws.com/event-platform-analytics-api:latest`
3. `410772457866.dkr.ecr.us-east-1.amazonaws.com/event-platform-processor:latest`
4. `410772457866.dkr.ecr.us-east-1.amazonaws.com/event-platform-prometheus:latest`

### Prometheus Dockerfile

**File**: `Dockerfile.prometheus`

**Multi-Stage Build**:

```dockerfile
# Stage 1: Get AWS CLI
FROM amazon/aws-cli:latest AS aws-cli

# Stage 2: Prometheus with AWS CLI
FROM prom/prometheus:v2.51.2

USER root

# Copy AWS CLI for ECS API calls
COPY --from=aws-cli /usr/local/aws-cli /usr/local/aws-cli
COPY --from=aws-cli /usr/local/bin/aws /usr/local/bin/aws

# Copy dynamic service discovery script
COPY infra/monitoring/update-prometheus-targets.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/update-prometheus-targets.sh

# Start with the update script
CMD ["/usr/local/bin/update-prometheus-targets.sh"]
```

**Why Multi-Stage?**
- Prometheus base image doesn't include AWS CLI
- Alpine package manager (`apk`) not available in base image
- Multi-stage build copies pre-built AWS CLI binaries
- Keeps final image size manageable

**Script Execution**:
The `update-prometheus-targets.sh` script:
1. Gets initial IPs and writes config
2. Starts Prometheus in background
3. Monitors for IP changes in loop
4. Reloads Prometheus when changes detected

### ECS Task Definition

**File**: `infra/ecs-task-definitions/prometheus-task.json`

**Key Configuration**:
```json
{
  "family": "event-platform-prometheus",
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::410772457866:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::410772457866:role/ecsTaskRole",
  "containerDefinitions": [{
    "name": "prometheus",
    "image": "410772457866.dkr.ecr.us-east-1.amazonaws.com/event-platform-prometheus:latest",
    "portMappings": [{"containerPort": 9090}],
    "environment": [
      {"name": "AWS_REGION", "value": "us-east-1"},
      {"name": "ECS_CLUSTER", "value": "event-platform-cluster"}
    ],
    "healthCheck": {
      "command": ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:9090/-/healthy || exit 1"],
      "interval": 30,
      "timeout": 5,
      "retries": 3,
      "startPeriod": 60
    }
  }]
}
```

**Health Check**:
- Checks `/-/healthy` endpoint every 30 seconds
- Allows 60 seconds for startup
- Ensures ALB routes traffic only to healthy instances

### Deployment Methods

#### Option 1: AWS CodeBuild (Automated)

**File**: `buildspec.yml`

**Process**:
1. Login to ECR
2. Build all Docker images
3. Push to ECR with `latest` and commit hash tags
4. Force new ECS deployments for all services

**Trigger**: Git push to GitHub repository

#### Option 2: Manual Deployment

```bash
# Build and push Prometheus image
docker build -f Dockerfile.prometheus -t 410772457866.dkr.ecr.us-east-1.amazonaws.com/event-platform-prometheus:latest .
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 410772457866.dkr.ecr.us-east-1.amazonaws.com
docker push 410772457866.dkr.ecr.us-east-1.amazonaws.com/event-platform-prometheus:latest

# Force new deployment
aws ecs update-service --cluster event-platform-cluster --service event-platform-prometheus --force-new-deployment --region us-east-1

# Wait for deployment (typically 2-3 minutes)
# Register new task IP with internal ALB target group
```

## Access and Usage

### Grafana Dashboard

**URL**: `http://event-platform-alb-95530675.us-east-1.elb.amazonaws.com:3000`

**Initial Setup**:
1. Login with `admin` / `admin`
2. Change password when prompted
3. Add Prometheus data source:
   - Name: `Prometheus`
   - URL: `http://internal-prometheus-internal-300523112.us-east-1.elb.amazonaws.com:9090`
   - Access: `Server (default)`
4. Import dashboard from `grafana-dashboard.json`

### Prometheus UI

**URL**: `http://event-platform-alb-95530675.us-east-1.elb.amazonaws.com:9090`

**Useful Queries**:

```promql
# Service availability
up

# Request rate (per second)
rate(http_requests_total[5m])

# Request latency (p95)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status_code=~"5.."}[5m])

# Kafka message throughput
rate(kafka_messages_sent_total[5m])

# DynamoDB operation latency
rate(dynamodb_operation_seconds_sum[5m]) / rate(dynamodb_operation_seconds_count[5m])
```

### API Metrics Endpoints

**Telemetry API**: `http://event-platform-alb-95530675.us-east-1.elb.amazonaws.com:8000/metrics`

**Analytics API**: `http://event-platform-alb-95530675.us-east-1.elb.amazonaws.com:8001/metrics`

## Troubleshooting

### Prometheus Not Showing Data

**Symptom**: Grafana shows "No data" for queries

**Checks**:
1. Verify Prometheus is running:
   ```bash
   aws ecs describe-services --cluster event-platform-cluster --services event-platform-prometheus --region us-east-1
   ```

2. Check Prometheus logs:
   ```bash
   aws logs tail /ecs/event-platform-prometheus --since 10m --follow --region us-east-1
   ```

3. Verify target IPs are correct:
   - Access Prometheus UI → Status → Targets
   - Compare with actual task IPs from ECS console

4. Test metrics endpoints directly:
   ```bash
   curl http://<task-ip>:8000/metrics
   ```

### Service Discovery Script Not Running

**Symptom**: Prometheus config not updating after service restarts

**Checks**:
1. Verify script is in container:
   ```bash
   aws ecs execute-command --cluster event-platform-cluster --task <task-id> --container prometheus --interactive --command "/bin/sh"
   # Inside container:
   ls -la /usr/local/bin/update-prometheus-targets.sh
   ```

2. Check for AWS CLI:
   ```bash
   aws --version
   ```

3. Verify IAM permissions:
   - Task role must have `ecs:ListTasks` and `ecs:DescribeTasks`

### Grafana Connection Issues

**Symptom**: "dial tcp: i/o timeout" when testing Prometheus data source

**Checks**:
1. Verify internal ALB is healthy:
   ```bash
   aws elbv2 describe-target-health --target-group-arn <prom-int-tg-arn> --region us-east-1
   ```

2. Check security group rules:
   - ECS tasks must allow traffic from themselves (self-referencing rule)

3. Verify Prometheus task is registered with internal ALB target group

### High Memory Usage

**Symptom**: Prometheus task restarting due to OOM

**Solution**:
- Increase task memory in task definition (currently 1024 MB)
- Reduce retention period in Prometheus config
- Reduce scrape interval (currently 15s)

### Missing Metrics

**Symptom**: Expected metrics not appearing in Prometheus

**Checks**:
1. Verify instrumentation in application code:
   - Python: Check `prometheus_fastapi_instrumentator` is installed
   - Check custom metrics are registered

2. Test `/metrics` endpoint returns expected metrics:
   ```bash
   curl http://<service-endpoint>/metrics | grep <metric-name>
   ```

3. Check Prometheus scrape configs match metric paths

## File Structure

```
project-root/
├── Dockerfile.prometheus              # Prometheus container with dynamic discovery
├── infra/
│   ├── ecs-task-definitions/
│   │   └── prometheus-task.json      # ECS task definition
│   └── monitoring/
│       └── update-prometheus-targets.sh  # Service discovery script
├── producer/
│   └── kafka.py                      # Kafka metrics instrumentation
├── consumer/
│   ├── dynamodb.py                   # DynamoDB metrics
│   └── s3.py                         # S3 metrics
├── grafana-dashboard.json            # Pre-configured dashboard
├── buildspec.yml                     # CodeBuild deployment config
└── MONITORING_SETUP.md              # This document
```

## Maintenance

### Regular Tasks

1. **Monitor CloudWatch Logs**: Check for errors in Prometheus logs
2. **Review Grafana Alerts**: Set up alerts for critical metrics
3. **Update Dashboards**: Add panels for new metrics as services evolve
4. **Check Costs**: Review CloudWatch, ECS, and ALB costs monthly

### Scaling Considerations

**Current Limitations**:
- Single Prometheus instance (no HA)
- Ephemeral storage (data lost on restart)
- Manual target registration with internal ALB

**Future Improvements**:
- Add Prometheus persistent storage (EFS or EBS)
- Implement high availability with Prometheus replicas
- Use AWS Service Discovery for automatic target registration
- Add alerting with Prometheus Alertmanager
- Implement metric retention policies

## Conclusion

This monitoring infrastructure provides:
- ✅ Real-time application metrics
- ✅ Automatic adaptation to service restarts
- ✅ Production-ready dashboards
- ✅ Secure AWS integration
- ✅ Cost-effective solution without CloudWatch Metrics

The dynamic service discovery implementation ensures monitoring remains functional despite the ephemeral nature of ECS Fargate tasks, providing reliable observability for the event-driven analytics platform.

