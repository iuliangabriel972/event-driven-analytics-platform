"""Pydantic schemas for telemetry ingestion."""
from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field


class TelemetryRequest(BaseModel):
    """Request schema for vehicle telemetry."""
    vehicle_id: str = Field(..., description="Vehicle identifier")
    driver_id: str = Field(..., description="Driver identifier")
    event_type: str = Field(..., description="Event type (e.g., acceleration, braking, cornering)")
    timestamp: datetime = Field(..., description="Event timestamp")
    data: Dict[str, Any] = Field(..., description="Telemetry data payload")


class TelemetryResponse(BaseModel):
    """Response schema for telemetry ingestion."""
    telemetry_id: UUID = Field(..., description="Unique telemetry record identifier")
    status: str = Field(default="accepted", description="Ingestion status")
    message: str = Field(default="Telemetry data accepted for processing", description="Status message")

