#!/usr/bin/env python3
"""Update Prometheus targets by querying ECS API."""
import json
import os
import subprocess
import sys

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
CLUSTER = os.getenv("ECS_CLUSTER", "event-platform-cluster")
TARGETS_DIR = "/etc/prometheus/targets"

os.makedirs(TARGETS_DIR, exist_ok=True)

def get_task_ip(service_name):
    """Get the first running task IP for a service."""
    try:
        # List tasks
        result = subprocess.run(
            ["aws", "ecs", "list-tasks", "--cluster", CLUSTER, 
             "--service-name", service_name, "--region", AWS_REGION,
             "--desired-status", "RUNNING"],
            capture_output=True, text=True, check=True
        )
        tasks = json.loads(result.stdout)
        if not tasks.get("taskArns"):
            return None
        
        task_arn = tasks["taskArns"][0]
        
        # Describe task
        result = subprocess.run(
            ["aws", "ecs", "describe-tasks", "--cluster", CLUSTER,
             "--tasks", task_arn, "--region", AWS_REGION],
            capture_output=True, text=True, check=True
        )
        task_details = json.loads(result.stdout)
        
        if task_details.get("tasks"):
            task = task_details["tasks"][0]
            if task.get("containers") and task["containers"][0].get("networkInterfaces"):
                return task["containers"][0]["networkInterfaces"][0].get("privateIpv4Address")
    except Exception as e:
        print(f"Error getting IP for {service_name}: {e}", file=sys.stderr)
    return None

def update_targets():
    """Update Prometheus target files."""
    # Telemetry API
    telemetry_ip = get_task_ip("event-platform-telemetry-api")
    if telemetry_ip:
        targets = [{"targets": [f"{telemetry_ip}:8000"], "labels": {"service": "telemetry-api"}}]
        with open(f"{TARGETS_DIR}/telemetry-api.json", "w") as f:
            json.dump(targets, f)
        print(f"Updated telemetry-api: {telemetry_ip}:8000")
    
    # Analytics API
    analytics_ip = get_task_ip("event-platform-analytics-api")
    if analytics_ip:
        targets = [{"targets": [f"{analytics_ip}:8001"], "labels": {"service": "analytics-api"}}]
        with open(f"{TARGETS_DIR}/analytics-api.json", "w") as f:
            json.dump(targets, f)
        print(f"Updated analytics-api: {analytics_ip}:8001")

if __name__ == "__main__":
    update_targets()

