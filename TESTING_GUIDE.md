# Testing Guide - GraphQL API and Grafana

## Testing GraphQL API

### Prerequisites

1. **Get ALB DNS**:
```powershell
aws elbv2 describe-load-balancers --region us-east-1 --query 'LoadBalancers[?contains(LoadBalancerName, `event-platform`)].DNSName' --output text
```

2. **Generate JWT Token**:
```powershell
.\scripts\generate_jwt_token.ps1
```

Or manually:
```powershell
python -c "import jwt; from datetime import datetime, timedelta, timezone; payload = {'sub': 'test-user', 'aud': 'event-platform', 'iat': int(datetime.now(timezone.utc).timestamp()), 'exp': int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())}; print(jwt.encode(payload, 'change-me-in-production-use-secrets-manager', algorithm='HS256'))"
```

### Method 1: Using PowerShell Script (Recommended)

```powershell
# Get ALB DNS
$albDns = aws elbv2 describe-load-balancers --region us-east-1 --query 'LoadBalancers[?contains(LoadBalancerName, `event-platform`)].DNSName' --output text

# Generate token
$token = .\scripts\generate_jwt_token.ps1

# Query GraphQL
.\scripts\query_graphql.ps1 -JwtToken $token -ApiUrl "http://${albDns}:8001" -Query "query { latestEvents(limit: 5) { eventId eventType userId timestamp } }"
```

### Method 2: Direct PowerShell Command

```powershell
$albDns = "event-platform-alb-95530675.us-east-1.elb.amazonaws.com"
$token = "YOUR_JWT_TOKEN"

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

# Latest Events
$query = @{
    query = "query { latestEvents(limit: 5) { eventId eventType userId timestamp } }"
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://${albDns}:8001/graphql" -Method Post -Headers $headers -Body $query
$response | ConvertTo-Json -Depth 10

# Events by Type
$query = @{
    query = "query { eventsByType(eventType: `"vehicle.location`") { eventId userId timestamp } }"
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://${albDns}:8001/graphql" -Method Post -Headers $headers -Body $query

# Events by User
$query = @{
    query = "query { eventsByUser(userId: `"user-001`") { eventId eventType timestamp } }"
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://${albDns}:8001/graphql" -Method Post -Headers $headers -Body $query
```

### Method 3: Using curl

```bash
# Get token first
TOKEN=$(python -c "import jwt; from datetime import datetime, timedelta, timezone; payload = {'sub': 'test-user', 'aud': 'event-platform', 'iat': int(datetime.now(timezone.utc).timestamp()), 'exp': int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())}; print(jwt.encode(payload, 'change-me-in-production-use-secrets-manager', algorithm='HS256'))")

# Query GraphQL
curl -X POST http://ALB_DNS:8001/graphql \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ latestEvents(limit: 5) { eventId eventType userId timestamp } }"}'
```

### Method 4: Using GraphQL Playground (Browser)

1. Open browser to: `http://ALB_DNS:8001/graphql`
2. In the HTTP Headers section, add:
```json
{
  "Authorization": "Bearer YOUR_JWT_TOKEN"
}
```
3. Enter your query:
```graphql
query {
  latestEvents(limit: 5) {
    eventId
    eventType
    userId
    timestamp
    payload
  }
}
```

### Example GraphQL Queries

#### Get Latest Events
```graphql
query {
  latestEvents(limit: 10) {
    eventId
    eventType
    userId
    timestamp
    payload
  }
}
```

#### Get Events by Type
```graphql
query {
  eventsByType(eventType: "vehicle.location") {
    eventId
    userId
    timestamp
  }
}
```

#### Get Events by User
```graphql
query {
  eventsByUser(userId: "user-001") {
    eventId
    eventType
    timestamp
  }
}
```

## Accessing Grafana

### Get Grafana URL

```powershell
# Check if Grafana has dedicated ALB
$grafanaAlb = aws elbv2 describe-load-balancers --region us-east-1 --query 'LoadBalancers[?contains(LoadBalancerName, `grafana`)].DNSName' --output text

if ($grafanaAlb) {
    Write-Host "Grafana URL: http://${grafanaAlb}:3000"
} else {
    # Use main ALB
    $mainAlb = aws elbv2 describe-load-balancers --region us-east-1 --query 'LoadBalancers[?contains(LoadBalancerName, `event-platform`)].DNSName' --output text
    Write-Host "Grafana URL: http://${mainAlb}:3000"
}
```

### Default Credentials

- **Username**: `admin`
- **Password**: `admin`

### Viewing Metrics in Grafana

1. **Access Grafana**: Open `http://ALB_DNS:3000` in browser
2. **Login** with admin/admin
3. **Add Prometheus Data Source** (if not already added):
   - Go to Configuration → Data Sources
   - Add Prometheus
   - URL: `http://prometheus-service:9090` (internal) or get Prometheus ALB DNS
4. **View Dashboards**:
   - Go to Dashboards → Browse
   - Import dashboard from `infra/monitoring/grafana-dashboard.json`
5. **Explore Metrics**:
   - Go to Explore section
   - Select Prometheus data source
   - Query examples:
     - `http_requests_total` - Total HTTP requests
     - `http_request_duration_seconds` - Request latency
     - `consumer_messages_processed_total` - Messages processed
     - `consumer_message_processing_seconds` - Processing time

### Viewing Logs

#### Option 1: CloudWatch Logs (Recommended)

```powershell
# Grafana logs
aws logs tail /ecs/event-platform-grafana --region us-east-1 --since 10m --format short

# Telemetry API logs
aws logs tail /ecs/event-platform-telemetry-api --region us-east-1 --since 10m --format short

# Processor logs
aws logs tail /ecs/event-platform-processor --region us-east-1 --since 10m --format short

# Analytics API logs
aws logs tail /ecs/event-platform-analytics-api --region us-east-1 --since 10m --format short

# Prometheus logs
aws logs tail /ecs/event-platform-prometheus --region us-east-1 --since 10m --format short
```

#### Option 2: Grafana Explore (for Metrics)

1. Go to **Explore** in Grafana
2. Select **Prometheus** data source
3. Enter query: `http_requests_total{service="telemetry-api"}`
4. View time series graph

#### Option 3: ECS Task Logs

```powershell
# Get running task ID
$taskId = aws ecs list-tasks --cluster event-platform-cluster --service-name event-platform-grafana --region us-east-1 --query 'taskArns[0]' --output text

# Get log stream
$logStream = aws ecs describe-tasks --cluster event-platform-cluster --tasks $taskId --region us-east-1 --query 'tasks[0].containers[0].logStreamName' --output text

# View logs
aws logs get-log-events --log-group-name /ecs/event-platform-grafana --log-stream-name $logStream --region us-east-1 --limit 50
```

### Prometheus Access

```powershell
# Get Prometheus URL
$prometheusAlb = aws elbv2 describe-load-balancers --region us-east-1 --query 'LoadBalancers[?contains(LoadBalancerName, `prometheus`)].DNSName' --output text

if ($prometheusAlb) {
    Write-Host "Prometheus: http://${prometheusAlb}:9090"
} else {
    $mainAlb = aws elbv2 describe-load-balancers --region us-east-1 --query 'LoadBalancers[?contains(LoadBalancerName, `event-platform`)].DNSName' --output text
    Write-Host "Prometheus: http://${mainAlb}:9090"
}
```

Access Prometheus UI:
- URL: `http://ALB_DNS:9090`
- View targets: `http://ALB_DNS:9090/targets`
- Query metrics: `http://ALB_DNS:9090/graph`

## Quick Test Script

Save this as `test-graphql-and-grafana.ps1`:

```powershell
# Test GraphQL API and Grafana Access

Write-Host "=== Testing GraphQL API ===" -ForegroundColor Green

# Get ALB DNS
$albDns = aws elbv2 describe-load-balancers --region us-east-1 --query 'LoadBalancers[?contains(LoadBalancerName, `event-platform`)].DNSName' --output text
Write-Host "ALB DNS: $albDns"

# Generate token
Write-Host "`nGenerating JWT token..."
$token = python -c "import jwt; from datetime import datetime, timedelta, timezone; payload = {'sub': 'test-user', 'aud': 'event-platform', 'iat': int(datetime.now(timezone.utc).timestamp()), 'exp': int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())}; print(jwt.encode(payload, 'change-me-in-production-use-secrets-manager', algorithm='HS256'))" 2>&1
$token = $token.Trim()

# Test GraphQL
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

$query = @{
    query = "query { latestEvents(limit: 3) { eventId eventType userId timestamp } }"
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "http://${albDns}:8001/graphql" -Method Post -Headers $headers -Body $query -ErrorAction Stop
    Write-Host "✅ GraphQL API is working!" -ForegroundColor Green
    Write-Host "Events found: $($response.data.latestEvents.Count)"
    $response.data.latestEvents | ForEach-Object {
        Write-Host "  - $($_.eventId): $($_.eventType) by $($_.userId)"
    }
} catch {
    Write-Host "❌ GraphQL API error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n=== Grafana Access ===" -ForegroundColor Green
Write-Host "Grafana URL: http://${albDns}:3000"
Write-Host "Username: admin"
Write-Host "Password: admin"
Write-Host "`nTo view logs, run:"
Write-Host "  aws logs tail /ecs/event-platform-grafana --region us-east-1 --since 10m"
```

## Troubleshooting

### GraphQL API Returns 401 Unauthorized

- Verify JWT token is valid and not expired
- Check token includes `aud: "event-platform"`
- Ensure `Authorization: Bearer TOKEN` header is set correctly

### GraphQL API Returns 404

- Verify ALB DNS is correct
- Check service is running: `aws ecs describe-services --cluster event-platform-cluster --services event-platform-analytics-api --region us-east-1`
- Verify port 8001 is accessible

### Cannot Access Grafana

- Check Grafana service is running
- Verify security group allows port 3000
- Check ALB listener configuration for port 3000
- Try accessing via task's public IP directly (if available)

### No Metrics in Grafana

- Verify Prometheus is running and scraping targets
- Check Prometheus data source is configured correctly
- Verify services are exposing `/metrics` endpoints
- Check Prometheus targets: `http://PROMETHEUS_URL:9090/targets`

