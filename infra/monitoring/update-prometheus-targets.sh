#!/bin/sh
set -e

echo "Starting Prometheus with dynamic service discovery..."

# Function to get current IPs
get_current_ips() {
    TELEMETRY_TASK=$(aws ecs list-tasks --cluster event-platform-cluster --service-name event-platform-telemetry-api --region us-east-1 --query 'taskArns[0]' --output text 2>/dev/null || echo "")
    if [ -n "$TELEMETRY_TASK" ]; then
        TELEMETRY_IP=$(aws ecs describe-tasks --cluster event-platform-cluster --tasks $TELEMETRY_TASK --region us-east-1 --query 'tasks[0].containers[0].networkInterfaces[0].privateIpv4Address' --output text 2>/dev/null || echo "")
    fi
    
    ANALYTICS_TASK=$(aws ecs list-tasks --cluster event-platform-cluster --service-name event-platform-analytics-api --region us-east-1 --query 'taskArns[0]' --output text 2>/dev/null || echo "")
    if [ -n "$ANALYTICS_TASK" ]; then
        ANALYTICS_IP=$(aws ecs describe-tasks --cluster event-platform-cluster --tasks $ANALYTICS_TASK --region us-east-1 --query 'tasks[0].containers[0].networkInterfaces[0].privateIpv4Address' --output text 2>/dev/null || echo "")
    fi
}

# Function to update config
update_config() {
    cat > /etc/prometheus/prometheus.yml <<EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "telemetry-api"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["${TELEMETRY_IP}:8000"]
        labels:
          service: telemetry-api
          environment: production

  - job_name: "analytics-api"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["${ANALYTICS_IP}:8001"]
        labels:
          service: analytics-api
          environment: production
EOF
}

# Get initial IPs
get_current_ips
LAST_TELEMETRY_IP="$TELEMETRY_IP"
LAST_ANALYTICS_IP="$ANALYTICS_IP"

echo "Initial IPs - Telemetry: $TELEMETRY_IP, Analytics: $ANALYTICS_IP"
update_config

# Start Prometheus in background
/bin/prometheus --config.file=/etc/prometheus/prometheus.yml \
                --storage.tsdb.path=/prometheus \
                --web.console.libraries=/usr/share/prometheus/console_libraries \
                --web.console.templates=/usr/share/prometheus/consoles \
                --web.enable-lifecycle &

PROMETHEUS_PID=$!
echo "Prometheus started (PID: $PROMETHEUS_PID)"

# Monitor for IP changes
while true; do
    sleep 60
    
    get_current_ips
    
    if [ "$TELEMETRY_IP" != "$LAST_TELEMETRY_IP" ] || [ "$ANALYTICS_IP" != "$LAST_ANALYTICS_IP" ]; then
        echo "IP change detected! Telemetry: $LAST_TELEMETRY_IP -> $TELEMETRY_IP, Analytics: $LAST_ANALYTICS_IP -> $ANALYTICS_IP"
        update_config
        
        # Reload Prometheus
        if wget --spider -q http://localhost:9090/-/healthy 2>/dev/null; then
            wget --post-data="" -q -O - http://localhost:9090/-/reload
            echo "Prometheus config reloaded"
        fi
        
        LAST_TELEMETRY_IP="$TELEMETRY_IP"
        LAST_ANALYTICS_IP="$ANALYTICS_IP"
    fi
done

