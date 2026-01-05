# Build and push all Docker images to ECR
Write-Host "=== BUILDING AND PUSHING DOCKER IMAGES TO ECR ===`n"

# Set AWS region
$REGION = "us-east-1"
$ACCOUNT_ID = "410772457866"

# Login to ECR
Write-Host "Logging into ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

# Build and push telemetry-api
Write-Host "`nBuilding telemetry-api..."
docker build -t event-platform-telemetry-api ./producer
Write-Host "Tagging telemetry-api..."
docker tag event-platform-telemetry-api:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/event-platform-telemetry-api:latest
Write-Host "Pushing telemetry-api..."
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/event-platform-telemetry-api:latest

# Build and push processor
Write-Host "`nBuilding processor..."
docker build -t event-platform-processor ./consumer
Write-Host "Tagging processor..."
docker tag event-platform-processor:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/event-platform-processor:latest
Write-Host "Pushing processor..."
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/event-platform-processor:latest

# Build and push analytics-api
Write-Host "`nBuilding analytics-api..."
docker build -t event-platform-analytics-api ./graphql_api
Write-Host "Tagging analytics-api..."
docker tag event-platform-analytics-api:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/event-platform-analytics-api:latest
Write-Host "Pushing analytics-api..."
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/event-platform-analytics-api:latest

# Build and push prometheus
Write-Host "`nBuilding prometheus..."
docker build -t event-platform-prometheus ./monitoring
Write-Host "Tagging prometheus..."
docker tag event-platform-prometheus:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/event-platform-prometheus:latest
Write-Host "Pushing prometheus..."
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/event-platform-prometheus:latest

Write-Host "`nâœ… ALL IMAGES BUILT AND PUSHED SUCCESSFULLY!"
