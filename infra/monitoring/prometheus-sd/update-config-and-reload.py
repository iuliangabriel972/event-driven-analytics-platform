#!/usr/bin/env python3
"""
Simple script that updates Prometheus config with current IPs and reloads Prometheus.
NO FILE-BASED DISCOVERY - just direct config updates.
"""
import boto3
import requests
import time
import sys

ECS_CLUSTER = "event-platform-cluster"
AWS_REGION = "us-east-1"

def get_task_ip(service_name):
    """Get private IP of running task for a service."""
    try:
        ecs = boto3.client("ecs", region_name=AWS_REGION)
        
        # List tasks
        tasks_response = ecs.list_tasks(
            cluster=ECS_CLUSTER,
            serviceName=service_name,
            desiredStatus="RUNNING"
        )
        
        if not tasks_response.get("taskArns"):
            return None
        
        task_arn = tasks_response["taskArns"][0]
        
        # Get task details
        tasks_detail = ecs.describe_tasks(
            cluster=ECS_CLUSTER,
            tasks=[task_arn]
        )
        
        if not tasks_detail.get("tasks"):
            return None
        
        # Extract private IP
        task = tasks_detail["tasks"][0]
        for container in task.get("containers", []):
            for ni in container.get("networkInterfaces", []):
                if "privateIpv4Address" in ni:
                    return ni["privateIpv4Address"]
        
        return None
    except Exception as e:
        print(f"Error getting IP for {service_name}: {e}", file=sys.stderr)
        return None

def update_config():
    """Update Prometheus config with current IPs."""
    telemetry_ip = get_task_ip("event-platform-telemetry-api")
    analytics_ip = get_task_ip("event-platform-analytics-api")
    
    if not telemetry_ip or not analytics_ip:
        print(f"Missing IPs: telemetry={telemetry_ip}, analytics={analytics_ip}")
        return False
    
    # Read template
    with open("/etc/prometheus/prometheus-template.yml", "r") as f:
        config = f.read()
    
    # Replace placeholders
    config = config.replace("TELEMETRY_API_IP", telemetry_ip)
    config = config.replace("ANALYTICS_API_IP", analytics_ip)
    
    # Write final config
    with open("/etc/prometheus/prometheus.yml", "w") as f:
        f.write(config)
    
    print(f"Updated config: telemetry={telemetry_ip}:8000, analytics={analytics_ip}:8001")
    
    # Debug: Print the actual config to verify it's correct
    print("--- Generated Config (first 30 lines) ---")
    for i, line in enumerate(config.split('\n')[:30], 1):
        print(f"{i:2d}: {line}")
    
    # Reload Prometheus
    try:
        response = requests.post("http://localhost:9090/-/reload", timeout=5)
        if response.status_code == 200:
            print("Prometheus reloaded successfully")
            return True
        else:
            print(f"Reload failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"Reload error: {e}")
        return False

if __name__ == "__main__":
    update_config()

