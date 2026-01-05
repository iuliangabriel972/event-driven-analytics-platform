# JWT Token Generator (for testing)
# Generates a test JWT token using the same secret as the API
# Usage: .\scripts\generate_jwt_token.ps1

param(
    [string]$Secret = "change-me-in-production-use-secrets-manager",
    [string]$Audience = "event-platform",
    [string]$Subject = "test-user",
    [int]$ExpirationMinutes = 60
)

# Check if python-jose is available
try {
    $pythonAvailable = python --version 2>&1
    Write-Host "Python found: $pythonAvailable" -ForegroundColor Green
}
catch {
    Write-Host "Python not found. Please install Python to generate JWT tokens." -ForegroundColor Red
    exit 1
}

# Create a temporary Python script to generate the token
$pythonScript = @"
from jose import jwt
from datetime import datetime, timedelta, timezone

secret = "$Secret"
audience = "$Audience"
subject = "$Subject"
expiration_minutes = $ExpirationMinutes

payload = {
    "sub": subject,
    "aud": audience,
    "iat": int(datetime.now(timezone.utc).timestamp()),
    "exp": int((datetime.now(timezone.utc) + timedelta(minutes=expiration_minutes)).timestamp())
}

token = jwt.encode(payload, secret, algorithm="HS256")
print(token)
"@

$tempScript = [System.IO.Path]::GetTempFileName() + ".py"
$pythonScript | Out-File -FilePath $tempScript -Encoding utf8

try {
    Write-Host "Generating JWT Token..." -ForegroundColor Cyan
    Write-Host "   Subject: $Subject" -ForegroundColor Cyan
    Write-Host "   Audience: $Audience" -ForegroundColor Cyan
    Write-Host "   Expires: $ExpirationMinutes minutes`n" -ForegroundColor Cyan
    
    # Try to install python-jose if not available
    try {
        python -c "from jose import jwt" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Module not found"
        }
    }
    catch {
        Write-Host "Installing python-jose..." -ForegroundColor Yellow
        pip install python-jose[cryptography] --quiet
    }
    
    $token = python $tempScript
    
    Write-Host "Token Generated:" -ForegroundColor Green
    Write-Host "`n$token`n" -ForegroundColor White
    
    Write-Host "Usage:" -ForegroundColor Cyan
    Write-Host "   .\scripts\generate_events.ps1 -JwtToken '$token'" -ForegroundColor White
    Write-Host "   .\scripts\query_graphql.ps1 -JwtToken '$token'`n" -ForegroundColor White
}
catch {
    Write-Host "Failed to generate token: $_" -ForegroundColor Red
    Write-Host "Alternative: Use a JWT tool like jwt.io to create tokens manually" -ForegroundColor Yellow
}
finally {
    if (Test-Path $tempScript) {
        Remove-Item $tempScript -Force
    }
}

