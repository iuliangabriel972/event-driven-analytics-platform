"""DynamoDB writer for storing normalized events."""
import json
import os
from typing import Optional

import aioboto3
from botocore.exceptions import ClientError

from consumer.models import EventModel
from shared.logger import get_logger

logger = get_logger(__name__)


class DynamoDBWriter:
    """Async DynamoDB writer for events."""
    
    def __init__(
        self,
        table_name: str,
        region_name: str = "us-east-1",
        aws_profile: Optional[str] = None,
    ):
        """
        Initialize DynamoDB writer.
        
        Args:
            table_name: DynamoDB table name
            region_name: AWS region
            aws_profile: AWS profile name (optional)
        """
        self.table_name = table_name
        self.region_name = region_name
        self.aws_profile = aws_profile or os.getenv("AWS_PROFILE")
        self.session = None
    
    async def _get_session(self):
        """Get or create boto3 session."""
        if self.session is None:
            session_kwargs = {"region_name": self.region_name}
            if self.aws_profile:
                session_kwargs["profile_name"] = self.aws_profile
            self.session = aioboto3.Session(**session_kwargs)
        return self.session
    
    def _ensure_no_floats(self, obj):
        """
        Recursively check and convert any remaining floats to Decimal.
        
        This is a safety check to ensure no floats reach DynamoDB,
        even if the model's conversion logic missed any.
        """
        from decimal import Decimal
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: self._ensure_no_floats(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._ensure_no_floats(item) for item in obj]
        else:
            return obj
    
    async def ensure_table_exists(self) -> None:
        """Create DynamoDB table if it doesn't exist (idempotent)."""
        session = await self._get_session()
        async with session.client("dynamodb") as dynamodb:
            try:
                # Check if table exists
                await dynamodb.describe_table(TableName=self.table_name)
                logger.info("dynamodb_table_exists", table_name=self.table_name)
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    # Create table
                    try:
                        await dynamodb.create_table(
                            TableName=self.table_name,
                            KeySchema=[
                                {"AttributeName": "event_id", "KeyType": "HASH"},  # Partition key
                                {"AttributeName": "timestamp", "KeyType": "RANGE"},  # Sort key
                            ],
                            AttributeDefinitions=[
                                {"AttributeName": "event_id", "AttributeType": "S"},
                                {"AttributeName": "timestamp", "AttributeType": "S"},
                                {"AttributeName": "event_type", "AttributeType": "S"},
                                {"AttributeName": "user_id", "AttributeType": "S"},
                            ],
                            GlobalSecondaryIndexes=[
                                {
                                    "IndexName": "event-type-index",
                                    "KeySchema": [
                                        {"AttributeName": "event_type", "KeyType": "HASH"},
                                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                                    ],
                                    "Projection": {"ProjectionType": "ALL"},
                                },
                                {
                                    "IndexName": "user-id-index",
                                    "KeySchema": [
                                        {"AttributeName": "user_id", "KeyType": "HASH"},
                                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                                    ],
                                    "Projection": {"ProjectionType": "ALL"},
                                },
                            ],
                            BillingMode="PAY_PER_REQUEST",  # Free tier friendly
                        )
                        logger.info("dynamodb_table_created", table_name=self.table_name)
                    except ClientError as create_error:
                        logger.error(
                            "dynamodb_table_creation_failed",
                            table_name=self.table_name,
                            error=str(create_error),
                        )
                        raise
                else:
                    raise
    
    async def write_event(self, event: EventModel) -> bool:
        """
        Write event to DynamoDB (idempotent).
        
        Args:
            event: Event model to write
            
        Returns:
            True if written, False if already exists
            
        Raises:
            ClientError: If DynamoDB operation fails (permissions, network, etc.)
        """
        session = await self._get_session()
        async with session.resource("dynamodb") as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            # Check if event already exists (idempotency)
            try:
                response = await table.get_item(
                    Key={
                        "event_id": str(event.event_id),
                        "timestamp": event.timestamp.isoformat(),
                    }
                )
                if "Item" in response:
                    logger.debug(
                        "event_already_exists",
                        event_id=str(event.event_id),
                        table_name=self.table_name,
                    )
                    return False
            except ClientError as e:
                # If get_item fails due to permissions or network issues, re-raise
                # to prevent breaking idempotency guarantee
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in ("ResourceNotFoundException", "ValidationException"):
                    # These are expected errors we can handle
                    logger.debug(
                        "dynamodb_get_item_expected_error",
                        event_id=str(event.event_id),
                        error_code=error_code,
                    )
                    # Continue to write - item doesn't exist
                else:
                    # Permission issues, throttling, network errors - re-raise
                    logger.error(
                        "dynamodb_get_item_failed",
                        event_id=str(event.event_id),
                        error_code=error_code,
                        error=str(e),
                    )
                    raise
            
            # Write event
            try:
                item = event.to_dynamodb_item()
                # Safety check: ensure no floats remain (DynamoDB doesn't support float type)
                item = self._ensure_no_floats(item)
                await table.put_item(Item=item)
                logger.info(
                    "event_written_to_dynamodb",
                    event_id=str(event.event_id),
                    event_type=event.event_type,
                    table_name=self.table_name,
                )
                return True
            except ClientError as e:
                error_msg = str(e)
                logger.error(
                    "dynamodb_write_failed",
                    event_id=str(event.event_id),
                    error=error_msg,
                )
                # If it's a float type error, log the item structure for debugging
                if "Float types are not supported" in error_msg:
                    logger.error("dynamodb_item_debug", item=json.dumps(item, default=str))
                raise

