"""Pydantic schemas for the Producer API."""
from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field


class EventRequest(BaseModel):
    """Request schema for incoming events."""
    event_type: str = Field(..., description="Type of event (e.g., 'page_view', 'click')")
    user_id: str = Field(..., description="User identifier")
    payload: Dict[str, Any] = Field(..., description="Event payload data")


class EventMetadata(BaseModel):
    """Event metadata added by the producer."""
    event_id: UUID = Field(..., description="Unique event identifier")
    timestamp: datetime = Field(..., description="Event timestamp in ISO format")


class EventEnvelope(BaseModel):
    """Complete event with metadata."""
    event_id: UUID
    timestamp: datetime
    event_type: str
    user_id: str
    payload: Dict[str, Any]


class EventResponse(BaseModel):
    """Response schema for event ingestion."""
    event_id: UUID = Field(..., description="Unique event identifier")
    status: str = Field(default="accepted", description="Event status")
    message: str = Field(default="Event accepted for processing", description="Status message")

