"""GraphQL schema for analytics API."""
import json
import os
from typing import List

import aioboto3
from boto3.dynamodb.conditions import Key
from strawberry import Schema, field, type

from src.shared.logger import get_logger

logger = get_logger(__name__)

DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "VehicleTelemetry")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_PROFILE = os.getenv("AWS_PROFILE")


@type
class TelemetryRecord:
    """GraphQL TelemetryRecord type."""
    telemetry_id: str
    vehicle_id: str
    driver_id: str
    event_type: str
    timestamp: str
    data: str  # JSON string


@type
class DrivingSession:
    """Driving session with aggregated metrics."""
    session_id: str
    driver_id: str
    vehicle_id: str
    start_time: str
    end_time: str
    metrics: str  # JSON string


@type
class Query:
    """GraphQL queries."""
    
    @field
    async def latest_telemetry(self, limit: int = 10) -> List[TelemetryRecord]:
        """Get latest telemetry records."""
        session_kwargs = {"region_name": AWS_REGION}
        if AWS_PROFILE:
            session_kwargs["profile_name"] = AWS_PROFILE
        
        session = aioboto3.Session(**session_kwargs)
        async with session.resource("dynamodb") as dynamodb:
            table = await dynamodb.Table(DYNAMODB_TABLE)
            
            try:
                response = await table.scan(Limit=limit * 2)
                items = response.get("Items", [])
                
                sorted_items = sorted(
                    items,
                    key=lambda x: x.get("timestamp", ""),
                    reverse=True,
                )[:limit]
                
                records = [
                    TelemetryRecord(
                        telemetry_id=item["telemetry_id"],
                        vehicle_id=item["vehicle_id"],
                        driver_id=item["driver_id"],
                        event_type=item["event_type"],
                        timestamp=item["timestamp"],
                        data=json.dumps(item["data"]),
                    )
                    for item in sorted_items
                ]
                
                logger.info("latest_telemetry_query", limit=limit, returned=len(records))
                return records
            except Exception as e:
                logger.error("query_failed", error=str(e))
                return []
    
    @field
    async def telemetry_by_driver(self, driver_id: str, limit: int = 50) -> List[TelemetryRecord]:
        """Get telemetry records for a specific driver."""
        session_kwargs = {"region_name": AWS_REGION}
        if AWS_PROFILE:
            session_kwargs["profile_name"] = AWS_PROFILE
        
        session = aioboto3.Session(**session_kwargs)
        async with session.resource("dynamodb") as dynamodb:
            table = await dynamodb.Table(DYNAMODB_TABLE)
            
            try:
                response = await table.query(
                    IndexName="driver-id-index",
                    KeyConditionExpression=Key("driver_id").eq(driver_id),
                    ScanIndexForward=False,
                    Limit=limit,
                )
                
                items = response.get("Items", [])
                records = [
                    TelemetryRecord(
                        telemetry_id=item["telemetry_id"],
                        vehicle_id=item["vehicle_id"],
                        driver_id=item["driver_id"],
                        event_type=item["event_type"],
                        timestamp=item["timestamp"],
                        data=json.dumps(item["data"]),
                    )
                    for item in items
                ]
                
                logger.info("telemetry_by_driver_query", driver_id=driver_id, returned=len(records))
                return records
            except Exception as e:
                logger.error("query_failed", error=str(e))
                return []
    
    @field
    async def telemetry_by_vehicle(self, vehicle_id: str, limit: int = 50) -> List[TelemetryRecord]:
        """Get telemetry records for a specific vehicle."""
        session_kwargs = {"region_name": AWS_REGION}
        if AWS_PROFILE:
            session_kwargs["profile_name"] = AWS_PROFILE
        
        session = aioboto3.Session(**session_kwargs)
        async with session.resource("dynamodb") as dynamodb:
            table = await dynamodb.Table(DYNAMODB_TABLE)
            
            try:
                response = await table.query(
                    IndexName="vehicle-id-index",
                    KeyConditionExpression=Key("vehicle_id").eq(vehicle_id),
                    ScanIndexForward=False,
                    Limit=limit,
                )
                
                items = response.get("Items", [])
                records = [
                    TelemetryRecord(
                        telemetry_id=item["telemetry_id"],
                        vehicle_id=item["vehicle_id"],
                        driver_id=item["driver_id"],
                        event_type=item["event_type"],
                        timestamp=item["timestamp"],
                        data=json.dumps(item["data"]),
                    )
                    for item in items
                ]
                
                logger.info("telemetry_by_vehicle_query", vehicle_id=vehicle_id, returned=len(records))
                return records
            except Exception as e:
                logger.error("query_failed", error=str(e))
                return []


schema = Schema(query=Query)

