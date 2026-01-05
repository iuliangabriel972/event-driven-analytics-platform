# Current Setup Status

## Working Configuration

**Original Cluster (from 2 weeks ago):**
- Cluster: `vehicle-telemetry-cluster`
- ALB: `vehicle-telemetry-alb-1172425630.us-east-1.elb.amazonaws.com`
- Services:
  - `telemetry-api-service` (port 8000)
  - `event-processor-service` (port 8002)
  - `analytics-api-service` (port 8001)
- Kafka: `i-0b06040690b07bc0d` (172.31.7.187:9092)

**New Cluster (created today):**
- Cluster: `event-platform-cluster`
- ALB: `event-platform-alb-95530675.us-east-1.elb.amazonaws.com`
- Services:
  - `event-platform-telemetry-api` (port 8000)
  - `event-platform-processor` (port 8002)
  - `event-platform-analytics-api` (port 8001)
  - `event-platform-grafana` (port 3000)
  - `event-platform-prometheus` (port 9090)

## Issue

The new cluster's ECS tasks are in VPC `vpc-0c24402bd62f72a82` (10.0.x.x), but Kafka is in VPC `vpc-0ae90651de9c9d63f` (172.31.x.x). They cannot communicate directly.

## Solution

**Use the original working cluster** which is already configured correctly:
- ALB: `vehicle-telemetry-alb-1172425630.us-east-1.elb.amazonaws.com`
- Port 8000: Telemetry API
- Port 8001: GraphQL API

## Testing

```powershell
# Generate JWT token
.\scripts\generate_jwt_token.ps1

# Send events (use token from above)
.\scripts\generate_events.ps1 -JwtToken 'YOUR_TOKEN' -Count 10

# Query GraphQL (use token from above)
.\scripts\query_graphql.ps1 -JwtToken 'YOUR_TOKEN'
```

## Next Steps

1. Either migrate Grafana/Prometheus to the original cluster, OR
2. Create VPC peering between the two VPCs, OR
3. Move Kafka to the same VPC as the new cluster

