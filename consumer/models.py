"""Data models for the consumer service."""
from datetime import datetime
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
        """Convert to DynamoDB item format."""
        return {
            "event_id": str(self.event_id),
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "user_id": self.user_id,
            "payload": self.payload,
        }
    
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

