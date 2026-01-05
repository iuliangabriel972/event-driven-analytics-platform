"""Data models for the consumer service."""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict
from uuid import UUID


class EventModel:
    """Event model for storage."""
    
    def __init__(
        self,
        event_id: UUID,
        timestamp: datetime,
        event_type: str,
        user_id: str,
        payload: Dict[str, Any],
    ):
        self.event_id = event_id
        self.timestamp = timestamp
        self.event_type = event_type
        self.user_id = user_id
        self.payload = payload
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format with Decimal types for numeric values."""
        # Convert payload dictionary, converting floats to Decimals
        converted_payload = self._convert_floats_to_decimal(self.payload)
        
        return {
            "event_id": str(self.event_id),
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "user_id": self.user_id,
            "payload": converted_payload,
        }
    
    def to_json_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary format (keeps floats as floats for S3)."""
        return {
            "event_id": str(self.event_id),
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "user_id": self.user_id,
            "payload": self.payload,
        }
    
    @staticmethod
    def _convert_floats_to_decimal(obj: Any) -> Any:
        """Recursively convert float values to Decimal for DynamoDB compatibility."""
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {key: EventModel._convert_floats_to_decimal(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [EventModel._convert_floats_to_decimal(item) for item in obj]
        else:
            return obj
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventModel":
        """Create EventModel from dictionary."""
        timestamp_str = data["timestamp"]
        # Handle ISO format with or without timezone
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str.replace("Z", "+00:00")
        elif "+" not in timestamp_str and timestamp_str.count("-") > 2:
            # Assume UTC if no timezone info
            timestamp_str = timestamp_str + "+00:00"
        
        return cls(
            event_id=UUID(data["event_id"]),
            timestamp=datetime.fromisoformat(timestamp_str),
            event_type=data["event_type"],
            user_id=data["user_id"],
            payload=data["payload"],
        )

