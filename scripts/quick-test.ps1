# Quick Test: GraphQL API and Grafana
$albDns = aws elbv2 describe-load-balancers --region us-east-1 --query 'LoadBalancers[?contains(LoadBalancerName, `event-platform`)].DNSName' --output text
Write-Host "ALB: $albDns`n"

# Generate token
$token = python -c "import jwt; from datetime import datetime, timedelta, timezone; payload = {'sub': 'test-user', 'aud': 'event-platform', 'iat': int(datetime.now(timezone.utc).timestamp()), 'exp': int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())}; print(jwt.encode(payload, 'change-me-in-production-use-secrets-manager', algorithm='HS256'))" 2>&1
$token = $token.Trim()

# Test GraphQL
$headers = @{ "Authorization" = "Bearer $token"; "Content-Type" = "application/json" }
$query = @{ query = "query { latestEvents(limit: 3) { eventId eventType userId } }" } | ConvertTo-Json
try {
    $response = Invoke-RestMethod -Uri "http://${albDns}:8001/graphql" -Method Post -Headers $headers -Body $query
    Write-Host "âœ… GraphQL API Working! Found $($response.data.latestEvents.Count) events"
} catch {
    Write-Host "âŒ Error: $($_.Exception.Message)"
}

Write-Host "`nGrafana: http://${albDns}:3000 (admin/admin)"
Write-Host "Logs: aws logs tail /ecs/event-platform-grafana --region us-east-1 --since 10m"
