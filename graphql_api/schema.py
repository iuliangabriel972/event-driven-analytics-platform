"""GraphQL schema definitions."""
import os
from datetime import datetime
from typing import List, Optional
from uuid import UUID

import aioboto3
from boto3.dynamodb.conditions import Key
from strawberry import Schema, field, type

from shared.logger import get_logger

logger = get_logger(__name__)

# Configuration
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "EventsHot")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_PROFILE = os.getenv("AWS_PROFILE")


@type
class Event:
    """GraphQL Event type."""
    event_id: str
    event_type: str
    user_id: str
    payload: dict
    timestamp: str


@type
class Query:
    """GraphQL queries."""
    
    @field
    async def latest_events(self, limit: int = 10) -> List[Event]:
        """
        Get the latest events.
        
        Args:
            limit: Maximum number of events to return (default: 10)
            
        Returns:
            List of Event objects
        """
        session_kwargs = {"region_name": AWS_REGION}
        if AWS_PROFILE:
            session_kwargs["profile_name"] = AWS_PROFILE
        
        session = aioboto3.Session(**session_kwargs)
        async with session.resource("dynamodb") as dynamodb:
            table = await dynamodb.Table(DYNAMODB_TABLE)
            
            try:
                # Scan table and sort by timestamp (not efficient for large tables, but works for demo)
                response = await table.scan(Limit=limit * 2)  # Get more to account for filtering
                items = response.get("Items", [])
                
                # Sort by timestamp descending and limit
                sorted_items = sorted(
                    items,
                    key=lambda x: x.get("timestamp", ""),
                    reverse=True,
                )[:limit]
                
                events = [
                    Event(
                        event_id=item["event_id"],
                        event_type=item["event_type"],
                        user_id=item["user_id"],
                        payload=item["payload"],
                        timestamp=item["timestamp"],
                    )
                    for item in sorted_items
                ]
                
                logger.info("latest_events_query", limit=limit, returned=len(events))
                return events
                
            except Exception as e:
                logger.error("latest_events_query_failed", error=str(e))
                return []
    
    @field
    async def events_by_type(self, event_type: str) -> List[Event]:
        """
        Get events filtered by event type.
        
        Args:
            event_type: Event type to filter by
            
        Returns:
            List of Event objects
        """
        session_kwargs = {"region_name": AWS_REGION}
        if AWS_PROFILE:
            session_kwargs["profile_name"] = AWS_PROFILE
        
        session = aioboto3.Session(**session_kwargs)
        async with session.resource("dynamodb") as dynamodb:
            table = await dynamodb.Table(DYNAMODB_TABLE)
            
            try:
                # Query using GSI
                response = await table.query(
                    IndexName="event-type-index",
                    KeyConditionExpression=Key("event_type").eq(event_type),
                    ScanIndexForward=False,  # Descending order
                )
                
                items = response.get("Items", [])
                events = [
                    Event(
                        event_id=item["event_id"],
                        event_type=item["event_type"],
                        user_id=item["user_id"],
                        payload=item["payload"],
                        timestamp=item["timestamp"],
                    )
                    for item in items
                ]
                
                logger.info(
                    "events_by_type_query",
                    event_type=event_type,
                    returned=len(events),
                )
                return events
                
            except Exception as e:
                logger.error(
                    "events_by_type_query_failed",
                    event_type=event_type,
                    error=str(e),
                )
                return []
    
    @field
    async def events_by_user(self, user_id: str) -> List[Event]:
        """
        Get events filtered by user ID.
        
        Args:
            user_id: User ID to filter by
            
        Returns:
            List of Event objects
        """
        session_kwargs = {"region_name": AWS_REGION}
        if AWS_PROFILE:
            session_kwargs["profile_name"] = AWS_PROFILE
        
        session = aioboto3.Session(**session_kwargs)
        async with session.resource("dynamodb") as dynamodb:
            table = await dynamodb.Table(DYNAMODB_TABLE)
            
            try:
                # Query using GSI
                response = await table.query(
                    IndexName="user-id-index",
                    KeyConditionExpression=Key("user_id").eq(user_id),
                    ScanIndexForward=False,  # Descending order
                )
                
                items = response.get("Items", [])
                events = [
                    Event(
                        event_id=item["event_id"],
                        event_type=item["event_type"],
                        user_id=item["user_id"],
                        payload=item["payload"],
                        timestamp=item["timestamp"],
                    )
                    for item in items
                ]
                
                logger.info(
                    "events_by_user_query",
                    user_id=user_id,
                    returned=len(events),
                )
                return events
                
            except Exception as e:
                logger.error(
                    "events_by_user_query_failed",
                    user_id=user_id,
                    error=str(e),
                )
                return []


schema = Schema(query=Query)

