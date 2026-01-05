# Event Generator Script
# Generates test events and sends them to the Telemetry API
# Usage: .\scripts\generate_events.ps1 -Count 10 -Interval 2

param(
    [int]$Count = 10,
    [int]$Interval = 2,  # seconds between events
    [string]$ApiUrl = "http://vehicle-telemetry-alb-1172425630.us-east-1.elb.amazonaws.com:8000",
    [string]$JwtToken = ""
)

# If no JWT token provided, generate a test token (for development only)
if ([string]::IsNullOrEmpty($JwtToken)) {
    Write-Host "⚠️  No JWT token provided. Generating a test token..." -ForegroundColor Yellow
    Write-Host "   For production, use: -JwtToken 'your-actual-jwt-token'" -ForegroundColor Yellow
    # For testing, you can use a simple token or skip auth temporarily
    $JwtToken = "test-token"
}

$headers = @{
    "Content-Type" = "application/json"
    "Authorization" = "Bearer $JwtToken"
}

$eventTypes = @("vehicle.location", "vehicle.speed", "vehicle.fuel", "vehicle.engine", "vehicle.battery")
$userIds = @("user-001", "user-002", "user-003")

Write-Host "`n🚀 Starting event generation..." -ForegroundColor Green
Write-Host "   API: $ApiUrl" -ForegroundColor Cyan
Write-Host "   Count: $Count events" -ForegroundColor Cyan
Write-Host "   Interval: $Interval seconds`n" -ForegroundColor Cyan

$successCount = 0
$failCount = 0

for ($i = 1; $i -le $Count; $i++) {
    $eventType = $eventTypes | Get-Random
    $userId = $userIds | Get-Random
    
    # Generate realistic payload based on event type
    $payload = switch ($eventType) {
        "vehicle.location" {
            @{
                latitude = [math]::Round((Get-Random -Minimum 40.0 -Maximum 50.0), 6)
                longitude = [math]::Round((Get-Random -Minimum -80.0 -Maximum -70.0), 6)
                altitude = Get-Random -Minimum 0 -Maximum 500
                accuracy = Get-Random -Minimum 5 -Maximum 20
            }
        }
        "vehicle.speed" {
            @{
                speed_kmh = Get-Random -Minimum 0 -Maximum 120
                speed_mph = [math]::Round((Get-Random -Minimum 0 -Maximum 120) * 0.621371, 2)
                acceleration = [math]::Round((Get-Random -Minimum -5.0 -Maximum 5.0), 2)
            }
        }
        "vehicle.fuel" {
            @{
                fuel_level_percent = Get-Random -Minimum 0 -Maximum 100
                fuel_consumption_l_100km = [math]::Round((Get-Random -Minimum 5.0 -Maximum 15.0), 2)
                range_km = Get-Random -Minimum 50 -Maximum 800
            }
        }
        "vehicle.engine" {
            @{
                rpm = Get-Random -Minimum 600 -Maximum 6000
                temperature_celsius = Get-Random -Minimum 80 -Maximum 110
                oil_pressure_psi = Get-Random -Minimum 20 -Maximum 60
            }
        }
        "vehicle.battery" {
            @{
                voltage = [math]::Round((Get-Random -Minimum 11.5 -Maximum 14.5), 2)
                current_amps = [math]::Round((Get-Random -Minimum -50.0 -Maximum 50.0), 2)
                state_of_charge_percent = Get-Random -Minimum 0 -Maximum 100
            }
        }
    }
    
    $body = @{
        event_type = $eventType
        user_id = $userId
        payload = $payload
    } | ConvertTo-Json -Depth 10
    
    try {
        $response = Invoke-RestMethod -Uri "$ApiUrl/events" -Method Post -Headers $headers -Body $body -ContentType "application/json" -ErrorAction Stop
        
        Write-Host "[$i/$Count] ✅ Event sent: $eventType (ID: $($response.event_id))" -ForegroundColor Green
        $successCount++
    }
    catch {
        Write-Host "[$i/$Count] ❌ Failed: $($_.Exception.Message)" -ForegroundColor Red
        $failCount++
        
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $responseBody = $reader.ReadToEnd()
            Write-Host "   Response: $responseBody" -ForegroundColor Red
        }
    }
    
    if ($i -lt $Count) {
        Start-Sleep -Seconds $Interval
    }
}

Write-Host "`nSummary:" -ForegroundColor Cyan
Write-Host "   Success: $successCount" -ForegroundColor Green
Write-Host "   Failed: $failCount" -ForegroundColor $(if ($failCount -gt 0) { "Red" } else { "Green" })
Write-Host "`nDone!`n" -ForegroundColor Green


