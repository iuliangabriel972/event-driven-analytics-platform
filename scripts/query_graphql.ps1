# GraphQL Query Script
# Queries the Analytics API GraphQL endpoint
# Usage: .\scripts\query_graphql.ps1 -Query "query { events { eventId } }"

param(
    [string]$Query = "query { latestEvents(limit: 10) { eventId eventType userId timestamp payload } }",
    [string]$ApiUrl = "http://vehicle-telemetry-alb-1172425630.us-east-1.elb.amazonaws.com:8001",
    [string]$JwtToken = ""
)

# If no JWT token provided, prompt or use test token
if ([string]::IsNullOrEmpty($JwtToken)) {
    Write-Host "No JWT token provided." -ForegroundColor Yellow
    Write-Host "   For production, use: -JwtToken 'your-actual-jwt-token'" -ForegroundColor Yellow
    Write-Host "   Attempting without token (will likely fail with 403)...`n" -ForegroundColor Yellow
    $JwtToken = "test-token"
}

$headers = @{
    "Content-Type" = "application/json"
}

if (-not [string]::IsNullOrEmpty($JwtToken)) {
    $headers["Authorization"] = "Bearer $JwtToken"
}

$body = @{
    query = $Query
} | ConvertTo-Json

Write-Host "Executing GraphQL Query..." -ForegroundColor Cyan
Write-Host "   API: $ApiUrl/graphql" -ForegroundColor Cyan
Write-Host "   Query: $Query`n" -ForegroundColor Cyan

try {
    $response = Invoke-RestMethod -Uri "$ApiUrl/graphql" -Method Post -Headers $headers -Body $body -ContentType "application/json" -ErrorAction Stop
    
    if ($response.data) {
        Write-Host "Success!`n" -ForegroundColor Green
        $response | ConvertTo-Json -Depth 10 | Write-Host
    }
    elseif ($response.errors) {
        Write-Host "GraphQL Errors:" -ForegroundColor Red
        $response.errors | ConvertTo-Json -Depth 10 | Write-Host
    }
    else {
        Write-Host "Response:" -ForegroundColor Cyan
        $response | ConvertTo-Json -Depth 10 | Write-Host
    }
}
catch {
    Write-Host "Request Failed: $($_.Exception.Message)" -ForegroundColor Red
    
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response Body:" -ForegroundColor Red
        Write-Host $responseBody
    }
}

Write-Host ""

