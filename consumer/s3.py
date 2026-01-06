"""S3 writer for storing raw event JSON."""
import json
import os
import time
from datetime import datetime
from typing import Optional

import aioboto3
from botocore.exceptions import ClientError
from prometheus_client import Counter, Histogram

from consumer.models import EventModel
from shared.logger import get_logger

logger = get_logger(__name__)

# Prometheus metrics
s3_uploads = Counter(
    "s3_uploads_total",
    "S3 upload operations",
    ["bucket", "status"]
)

s3_upload_duration = Histogram(
    "s3_upload_seconds",
    "S3 upload latency",
    ["bucket"]
)


class S3Writer:
    """Async S3 writer for raw events."""
    
    def __init__(
        self,
        bucket_name: str,
        region_name: str = "us-east-1",
        aws_profile: Optional[str] = None,
    ):
        """
        Initialize S3 writer.
        
        Args:
            bucket_name: S3 bucket name
            region_name: AWS region
            aws_profile: AWS profile name (optional)
        """
        self.bucket_name = bucket_name
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
    
    async def ensure_bucket_exists(self) -> None:
        """Create S3 bucket if it doesn't exist (idempotent)."""
        session = await self._get_session()
        async with session.client("s3") as s3:
            try:
                # Check if bucket exists
                await s3.head_bucket(Bucket=self.bucket_name)
                logger.info("s3_bucket_exists", bucket_name=self.bucket_name)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in ("404", "NoSuchBucket"):
                    # Create bucket
                    try:
                        create_kwargs = {"Bucket": self.bucket_name}
                        if self.region_name != "us-east-1":
                            create_kwargs["CreateBucketConfiguration"] = {
                                "LocationConstraint": self.region_name
                            }
                        await s3.create_bucket(**create_kwargs)
                        logger.info("s3_bucket_created", bucket_name=self.bucket_name)
                    except ClientError as create_error:
                        logger.error(
                            "s3_bucket_creation_failed",
                            bucket_name=self.bucket_name,
                            error=str(create_error),
                        )
                        raise
                else:
                    raise
    
    def _generate_key(self, event: EventModel) -> str:
        """
        Generate S3 key for event.
        
        Pattern: events/{year}/{month}/{day}/{event_id}.json
        
        Args:
            event: Event model
            
        Returns:
            S3 key string
        """
        timestamp = event.timestamp
        return f"events/{timestamp.year}/{timestamp.month:02d}/{timestamp.day:02d}/{event.event_id}.json"
    
    async def write_event(self, event: EventModel) -> bool:
        """
        Write raw event JSON to S3.
        
        Uses to_json_dict() to preserve floats (not Decimals) in S3.
        S3 stores raw JSON for analytics/archival, while DynamoDB uses Decimals.
        
        Args:
            event: Event model to write
            
        Returns:
            True if successful, False otherwise
        """
        start_time = time.time()
        session = await self._get_session()
        async with session.client("s3") as s3:
            try:
                key = self._generate_key(event)
                # Use to_json_dict() to keep floats (not Decimals) in S3
                event_json = json.dumps(event.to_json_dict(), default=str)
                
                await s3.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=event_json.encode("utf-8"),
                    ContentType="application/json",
                )
                
                duration = time.time() - start_time
                s3_upload_duration.labels(bucket=self.bucket_name).observe(duration)
                s3_uploads.labels(bucket=self.bucket_name, status="success").inc()
                
                logger.info(
                    "event_written_to_s3",
                    event_id=str(event.event_id),
                    bucket_name=self.bucket_name,
                    key=key,
                    duration_ms=round(duration * 1000, 2),
                )
                return True
            except ClientError as e:
                duration = time.time() - start_time
                s3_upload_duration.labels(bucket=self.bucket_name).observe(duration)
                s3_uploads.labels(bucket=self.bucket_name, status="error").inc()
                logger.error(
                    "s3_write_failed",
                    event_id=str(event.event_id),
                    error=str(e),
                )
                return False

