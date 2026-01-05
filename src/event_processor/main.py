"""Event processor service."""
import asyncio
import json
import os
import signal
import time
from typing import Optional

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

from src.event_processor.models import TelemetryRecord
from src.event_processor.storage import DynamoDBWriter, S3Writer
from src.shared.logger import configure_logging, get_logger

configure_logging(environment=os.getenv("ENVIRONMENT", "development"))
logger = get_logger(__name__)

# Configuration
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "vehicle-telemetry")
CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "telemetry-processors")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "VehicleTelemetry")
S3_BUCKET = os.getenv("S3_BUCKET", "vehicle-telemetry-raw")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_PROFILE = os.getenv("AWS_PROFILE")

# Initialize storage
dynamodb_writer = DynamoDBWriter(
    table_name=DYNAMODB_TABLE,
    region_name=AWS_REGION,
    aws_profile=AWS_PROFILE,
)
s3_writer = S3Writer(
    bucket_name=S3_BUCKET,
    region_name=AWS_REGION,
    aws_profile=AWS_PROFILE,
)

consumer: Optional[AIOKafkaConsumer] = None
shutdown_event = asyncio.Event()


async def process_message(message_value: dict) -> bool:
    """Process a telemetry message."""
    try:
        record = TelemetryRecord.from_dict(message_value)
        
        # Write to DynamoDB
        dynamodb_success = await dynamodb_writer.write_record(record)
        
        # Write to S3 (graceful degradation)
        s3_success = await s3_writer.write_record(record)
        if not s3_success:
            logger.warning("s3_write_failed_continuing", telemetry_id=str(record.telemetry_id))
        
        logger.info(
            "telemetry_processed",
            telemetry_id=str(record.telemetry_id),
            vehicle_id=record.vehicle_id,
            driver_id=record.driver_id,
            event_type=record.event_type,
        )
        
        return True
    except Exception as e:
        logger.error("processing_failed", error=str(e))
        return False


async def consume_messages() -> None:
    """Main consumer loop."""
    global consumer
    
    try:
        consumer = AIOKafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id=CONSUMER_GROUP,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        
        await consumer.start()
        logger.info("consumer_started", topic=KAFKA_TOPIC, consumer_group=CONSUMER_GROUP)
        
        # Ensure storage exists
        await dynamodb_writer.ensure_table_exists()
        await s3_writer.ensure_bucket_exists()
        
        async for message in consumer:
            if shutdown_event.is_set():
                break
            
            try:
                success = await process_message(message.value)
                if success:
                    await consumer.commit()
            except Exception as e:
                logger.error("message_processing_exception", error=str(e))
    
    except KafkaError as e:
        logger.error("kafka_error", error=str(e))
        raise
    finally:
        if consumer:
            await consumer.stop()
            logger.info("consumer_stopped")


def setup_signal_handlers() -> None:
    """Setup signal handlers."""
    def signal_handler(sig, frame):
        logger.info("shutdown_signal_received", signal=sig)
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main() -> None:
    """Main entry point."""
    setup_signal_handlers()
    
    try:
        await consume_messages()
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt")
    except Exception as e:
        logger.error("fatal_error", error=str(e))
        raise
    finally:
        logger.info("shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())

