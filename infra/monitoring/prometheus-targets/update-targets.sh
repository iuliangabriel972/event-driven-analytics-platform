#!/bin/bash
# Script to update Prometheus targets by querying ECS API
# This runs as a sidecar container or cron job

AWS_REGION=${AWS_REGION:-us-east-1}
CLUSTER=${CLUSTER:-event-platform-cluster}
TARGETS_DIR=${TARGETS_DIR:-/etc/prometheus/targets}

mkdir -p $TARGETS_DIR

# Get Telemetry API task IP
TELEMETRY_TASK=$(aws ecs list-tasks --cluster $CLUSTER --service-name event-platform-telemetry-api --region $AWS_REGION --query 'taskArns[0]' --output text)
if [ "$TELEMETRY_TASK" != "None" ] && [ -n "$TELEMETRY_TASK" ]; then
  TELEMETRY_IP=$(aws ecs describe-tasks --cluster $CLUSTER --tasks $TELEMETRY_TASK --region $AWS_REGION --query 'tasks[0].containers[0].networkInterfaces[0].privateIpv4Address' --output text)
  echo "[{\"targets\":[\"$TELEMETRY_IP:8000\"],\"labels\":{\"service\":\"telemetry-api\"}}]" > $TARGETS_DIR/telemetry-api.json
fi

# Get Analytics API task IP
ANALYTICS_TASK=$(aws ecs list-tasks --cluster $CLUSTER --service-name event-platform-analytics-api --region $AWS_REGION --query 'taskArns[0]' --output text)
if [ "$ANALYTICS_TASK" != "None" ] && [ -n "$ANALYTICS_TASK" ]; then
  ANALYTICS_IP=$(aws ecs describe-tasks --cluster $CLUSTER --tasks $ANALYTICS_TASK --region $AWS_REGION --query 'tasks[0].containers[0].networkInterfaces[0].privateIpv4Address' --output text)
  echo "[{\"targets\":[\"$ANALYTICS_IP:8001\"],\"labels\":{\"service\":\"analytics-api\"}}]" > $TARGETS_DIR/analytics-api.json
fi

