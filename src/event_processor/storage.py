"""Storage handlers for DynamoDB and S3."""
import json
import os
from typing import Optional

import aioboto3
from botocore.exceptions import ClientError

from src.event_processor.models import TelemetryRecord
from src.shared.logger import get_logger

logger = get_logger(__name__)


class DynamoDBWriter:
    """DynamoDB writer for telemetry records."""
    
    def __init__(self, table_name: str, region_name: str = "us-east-1", aws_profile: Optional[str] = None):
        self.table_name = table_name
        self.region_name = region_name
        self.aws_profile = aws_profile or os.getenv("AWS_PROFILE")
        self.session = None
    
    async def _get_session(self):
        if self.session is None:
            session_kwargs = {"region_name": self.region_name}
            if self.aws_profile:
                session_kwargs["profile_name"] = self.aws_profile
            self.session = aioboto3.Session(**session_kwargs)
        return self.session
    
    async def ensure_table_exists(self) -> None:
        """Create DynamoDB table if it doesn't exist."""
        session = await self._get_session()
        async with session.client("dynamodb") as dynamodb:
            try:
                await dynamodb.describe_table(TableName=self.table_name)
                logger.info("dynamodb_table_exists", table_name=self.table_name)
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    try:
                        await dynamodb.create_table(
                            TableName=self.table_name,
                            KeySchema=[
                                {"AttributeName": "telemetry_id", "KeyType": "HASH"},
                                {"AttributeName": "timestamp", "KeyType": "RANGE"},
                            ],
                            AttributeDefinitions=[
                                {"AttributeName": "telemetry_id", "AttributeType": "S"},
                                {"AttributeName": "timestamp", "AttributeType": "S"},
                                {"AttributeName": "driver_id", "AttributeType": "S"},
                                {"AttributeName": "vehicle_id", "AttributeType": "S"},
                            ],
                            GlobalSecondaryIndexes=[
                                {
                                    "IndexName": "driver-id-index",
                                    "KeySchema": [
                                        {"AttributeName": "driver_id", "KeyType": "HASH"},
                                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                                    ],
                                    "Projection": {"ProjectionType": "ALL"},
                                },
                                {
                                    "IndexName": "vehicle-id-index",
                                    "KeySchema": [
                                        {"AttributeName": "vehicle_id", "KeyType": "HASH"},
                                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                                    ],
                                    "Projection": {"ProjectionType": "ALL"},
                                },
                            ],
                            BillingMode="PAY_PER_REQUEST",
                        )
                        logger.info("dynamodb_table_created", table_name=self.table_name)
                    except ClientError as create_error:
                        logger.error("dynamodb_creation_failed", error=str(create_error))
                        raise
                else:
                    raise
    
    async def write_record(self, record: TelemetryRecord) -> bool:
        """Write telemetry record to DynamoDB."""
        session = await self._get_session()
        async with session.resource("dynamodb") as dynamodb:
            table = await dynamodb.Table(self.table_name)
            
            try:
                # Check if record exists (idempotency)
                response = await table.get_item(
                    Key={
                        "telemetry_id": str(record.telemetry_id),
                        "timestamp": record.timestamp.isoformat(),
                    }
                )
                if "Item" in response:
                    logger.debug("record_exists", telemetry_id=str(record.telemetry_id))
                    return False
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code not in ("ResourceNotFoundException", "ValidationException"):
                    logger.error("dynamodb_get_failed", error_code=error_code)
                    raise
            
            try:
                await table.put_item(Item=record.to_dynamodb_item())
                logger.info("record_written", telemetry_id=str(record.telemetry_id), driver_id=record.driver_id)
                return True
            except ClientError as e:
                logger.error("dynamodb_write_failed", error=str(e))
                raise


class S3Writer:
    """S3 writer for raw telemetry data."""
    
    def __init__(self, bucket_name: str, region_name: str = "us-east-1", aws_profile: Optional[str] = None):
        self.bucket_name = bucket_name
        self.region_name = region_name
        self.aws_profile = aws_profile or os.getenv("AWS_PROFILE")
        self.session = None
    
    async def _get_session(self):
        if self.session is None:
            session_kwargs = {"region_name": self.region_name}
            if self.aws_profile:
                session_kwargs["profile_name"] = self.aws_profile
            self.session = aioboto3.Session(**session_kwargs)
        return self.session
    
    async def ensure_bucket_exists(self) -> None:
        """Create S3 bucket if it doesn't exist."""
        session = await self._get_session()
        async with session.client("s3") as s3:
            try:
                await s3.head_bucket(Bucket=self.bucket_name)
                logger.info("s3_bucket_exists", bucket_name=self.bucket_name)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in ("404", "NoSuchBucket"):
                    try:
                        create_kwargs = {"Bucket": self.bucket_name}
                        if self.region_name != "us-east-1":
                            create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": self.region_name}
                        await s3.create_bucket(**create_kwargs)
                        logger.info("s3_bucket_created", bucket_name=self.bucket_name)
                    except ClientError as create_error:
                        logger.error("s3_creation_failed", error=str(create_error))
                        raise
    
    async def write_record(self, record: TelemetryRecord) -> bool:
        """Write raw telemetry record to S3."""
        session = await self._get_session()
        async with session.client("s3") as s3:
            try:
                timestamp = record.timestamp
                key = f"telemetry/{timestamp.year}/{timestamp.month:02d}/{timestamp.day:02d}/{record.telemetry_id}.json"
                
                record_json = json.dumps(record.to_dynamodb_item(), default=str)
                await s3.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=record_json.encode("utf-8"),
                    ContentType="application/json",
                )
                
                logger.info("record_written_to_s3", telemetry_id=str(record.telemetry_id), key=key)
                return True
            except ClientError as e:
                logger.error("s3_write_failed", error=str(e))
                return False

