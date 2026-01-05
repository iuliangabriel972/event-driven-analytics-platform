# Quick GraphQL Test Script
# Generates token and tests GraphQL API

Write-Host "=== Testing GraphQL API ===" -ForegroundColor Green
Write-Host ""

# Install python-jose if needed
Write-Host "Checking python-jose..." -ForegroundColor Cyan
pip install python-jose[cryptography] --quiet 2>&1 | Out-Null

# Generate JWT token
Write-Host "Generating JWT token..." -ForegroundColor Cyan
$token = python -c "from jose import jwt; from datetime import datetime, timedelta, timezone; payload = {'sub': 'test-user', 'aud': 'event-platform', 'iat': int(datetime.now(timezone.utc).timestamp()), 'exp': int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())}; print(jwt.encode(payload, 'change-me-in-production-use-secrets-manager', algorithm='HS256'))" 2>&1
$token = $token.Trim()

if ([string]::IsNullOrEmpty($token)) {
    Write-Host "Failed to generate token" -ForegroundColor Red
    exit 1
}

Write-Host "Token generated: $($token.Substring(0, [Math]::Min(30, $token.Length)))..." -ForegroundColor Green
Write-Host ""

# Test GraphQL API
Write-Host "Testing GraphQL API..." -ForegroundColor Cyan
$albDns = "vehicle-telemetry-alb-1172425630.us-east-1.elb.amazonaws.com"
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

$query = @{
    query = "query { latestEvents(limit: 5) { eventId eventType userId timestamp } }"
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "http://${albDns}:8001/graphql" -Method Post -Headers $headers -Body $query -ErrorAction Stop
    
    Write-Host "✅ GraphQL API is working!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Events found: $($response.data.latestEvents.Count)" -ForegroundColor Cyan
    
    if ($response.data.latestEvents.Count -gt 0) {
        Write-Host ""
        Write-Host "Events:" -ForegroundColor Yellow
        $response.data.latestEvents | ForEach-Object {
            Write-Host "  - $($_.eventId): $($_.eventType) by $($_.userId) at $($_.timestamp)"
        }
    } else {
        Write-Host ""
        Write-Host "No events found. Send some events first:" -ForegroundColor Yellow
        Write-Host "  .\generate_events.ps1 -JwtToken '$token' -Count 10" -ForegroundColor White
    }
} catch {
    Write-Host "❌ Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response: $responseBody" -ForegroundColor Red
    }
}

Write-Host ""


