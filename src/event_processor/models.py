"""Data models for event processing."""
from datetime import datetime
from typing import Any, Dict
from uuid import UUID


class TelemetryRecord:
    """Telemetry record model."""
    
    def __init__(
        self,
        telemetry_id: UUID,
        ingestion_timestamp: datetime,
        vehicle_id: str,
        driver_id: str,
        event_type: str,
        timestamp: datetime,
        data: Dict[str, Any],
    ):
        self.telemetry_id = telemetry_id
        self.ingestion_timestamp = ingestion_timestamp
        self.vehicle_id = vehicle_id
        self.driver_id = driver_id
        self.event_type = event_type
        self.timestamp = timestamp
        self.data = data
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            "telemetry_id": str(self.telemetry_id),
            "ingestion_timestamp": self.ingestion_timestamp.isoformat(),
            "vehicle_id": self.vehicle_id,
            "driver_id": self.driver_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelemetryRecord":
        """Create TelemetryRecord from dictionary."""
        timestamp_str = data["timestamp"]
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str.replace("Z", "+00:00")
        elif "+" not in timestamp_str:
            timestamp_str = timestamp_str + "+00:00"
        
        ingestion_str = data.get("ingestion_timestamp", data["timestamp"])
        if ingestion_str.endswith("Z"):
            ingestion_str = ingestion_str.replace("Z", "+00:00")
        elif "+" not in ingestion_str:
            ingestion_str = ingestion_str + "+00:00"
        
        return cls(
            telemetry_id=UUID(data["telemetry_id"]),
            ingestion_timestamp=datetime.fromisoformat(ingestion_str),
            vehicle_id=data["vehicle_id"],
            driver_id=data["driver_id"],
            event_type=data["event_type"],
            timestamp=datetime.fromisoformat(timestamp_str),
            data=data["data"],
        )

