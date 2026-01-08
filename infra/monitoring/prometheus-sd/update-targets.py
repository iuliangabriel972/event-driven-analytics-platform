#!/usr/bin/env python3
"""Update Prometheus targets by querying ECS API."""
import json
import os
import subprocess
import sys
from datetime import datetime

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
CLUSTER = os.getenv("ECS_CLUSTER", "event-platform-cluster")
TARGETS_DIR = "/etc/prometheus/targets"

# Ensure targets directory exists
os.makedirs(TARGETS_DIR, exist_ok=True)

def log(message):
    """Log with timestamp."""
    print(f"[{datetime.utcnow().isoformat()}Z] {message}", file=sys.stderr)

def get_task_ip(service_name):
    """Get the first running task IP for a service."""
    try:
        # List tasks - get all running tasks
        result = subprocess.run(
            ["aws", "ecs", "list-tasks", "--cluster", CLUSTER, 
             "--service-name", service_name, "--region", AWS_REGION,
             "--desired-status", "RUNNING"],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode != 0:
            log(f"Failed to list tasks for {service_name}: {result.stderr}")
            return None
            
        tasks = json.loads(result.stdout)
        if not tasks.get("taskArns") or len(tasks["taskArns"]) == 0:
            log(f"No running tasks found for {service_name}")
            return None
        
        task_arn = tasks["taskArns"][0]
        log(f"Found task for {service_name}: {task_arn}")
        
        # Describe task
        result = subprocess.run(
            ["aws", "ecs", "describe-tasks", "--cluster", CLUSTER,
             "--tasks", task_arn, "--region", AWS_REGION],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode != 0:
            log(f"Failed to describe task for {service_name}: {result.stderr}")
            return None
            
        task_details = json.loads(result.stdout)
        
        if not task_details.get("tasks") or len(task_details["tasks"]) == 0:
            log(f"No task details returned for {service_name}")
            return None
            
        task = task_details["tasks"][0]
        
        # Check if task is actually running
        if task.get("lastStatus") != "RUNNING":
            log(f"Task {task_arn} is not RUNNING (status: {task.get('lastStatus')})")
            return None
        
        # Get IP from network interfaces
        if task.get("containers") and len(task["containers"]) > 0:
            container = task["containers"][0]
            if container.get("networkInterfaces") and len(container["networkInterfaces"]) > 0:
                ip = container["networkInterfaces"][0].get("privateIpv4Address")
                if ip:
                    log(f"Found IP for {service_name}: {ip}")
                    return ip
        
        log(f"No IP found in task details for {service_name}")
        return None
        
    except subprocess.TimeoutExpired:
        log(f"Timeout getting IP for {service_name}")
        return None
    except Exception as e:
        log(f"Error getting IP for {service_name}: {e}")
        return None

def update_targets():
    """Update Prometheus target files."""
    updated = False
    
    # Telemetry API
    telemetry_ip = get_task_ip("event-platform-telemetry-api")
    target_file = f"{TARGETS_DIR}/telemetry-api.json"
    if telemetry_ip:
        targets = [{"targets": [f"{telemetry_ip}:8000"], "labels": {"service": "telemetry-api", "environment": "production"}}]
        with open(target_file, "w") as f:
            json.dump(targets, f, indent=2)
        log(f"✅ Updated telemetry-api: {telemetry_ip}:8000")
        updated = True
    else:
        log(f"⚠️  Could not update telemetry-api - service not found or not running")
        # Write empty array (valid JSON) to avoid stale data
        with open(target_file, "w") as f:
            json.dump([], f, indent=2)
    
    # Analytics API
    analytics_ip = get_task_ip("event-platform-analytics-api")
    target_file = f"{TARGETS_DIR}/analytics-api.json"
    if analytics_ip:
        targets = [{"targets": [f"{analytics_ip}:8001"], "labels": {"service": "analytics-api", "environment": "production"}}]
        with open(target_file, "w") as f:
            json.dump(targets, f, indent=2)
        log(f"✅ Updated analytics-api: {analytics_ip}:8001")
        updated = True
    else:
        log(f"⚠️  Could not update analytics-api - service not found or not running")
        # Write empty array (valid JSON) to avoid stale data
        with open(target_file, "w") as f:
            json.dump([], f, indent=2)
    
    if updated:
        log("✅ Service discovery update complete")
    else:
        log("⚠️  No services updated - check if services are running")

if __name__ == "__main__":
    update_targets()

