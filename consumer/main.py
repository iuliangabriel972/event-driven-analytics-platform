"""Consumer service for processing events from Kafka."""
import asyncio
import json
import os
import signal
import time
from typing import Optional

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError

from consumer.dynamodb import DynamoDBWriter
from consumer.models import EventModel
from consumer.s3 import S3Writer
from shared.logger import configure_logging, get_logger

# Configure logging
configure_logging(environment=os.getenv("ENVIRONMENT", "development"))
logger = get_logger(__name__)

# Configuration
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "events.raw")
KAFKA_DLQ_TOPIC = os.getenv("KAFKA_DLQ_TOPIC", "events.dlq")
CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "event-processors")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "EventsHot")
S3_BUCKET = os.getenv("S3_BUCKET", "event-platform-raw-events")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_PROFILE = os.getenv("AWS_PROFILE")

# Initialize writers
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

# Global consumer and DLQ producer
consumer: Optional[AIOKafkaConsumer] = None
dlq_producer: Optional[AIOKafkaProducer] = None
shutdown_event = asyncio.Event()


async def send_to_dlq(message_value: dict, error: str) -> None:
    """
    Send failed message to dead letter queue.
    
    Args:
        message_value: Original message value
        error: Error message
    """
    global dlq_producer
    
    if dlq_producer is None:
        try:
            dlq_producer = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await dlq_producer.start()
            logger.info("dlq_producer_started", topic=KAFKA_DLQ_TOPIC)
        except Exception as e:
            logger.error("dlq_producer_startup_failed", error=str(e))
            return
    
    try:
        dlq_message = {
            **message_value,
            "_dlq_metadata": {
                "original_topic": KAFKA_TOPIC,
                "error": error,
                "timestamp": str(time.time()),
            },
        }
        await dlq_producer.send_and_wait(KAFKA_DLQ_TOPIC, dlq_message)
        logger.warning(
            "message_sent_to_dlq",
            event_id=str(message_value.get("event_id")),
            error=error,
        )
    except Exception as e:
        logger.error("dlq_send_failed", error=str(e))


async def process_message(message_value: dict) -> bool:
    """
    Process a single event message.
    
    Args:
        message_value: Decoded message value
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Parse event
        event = EventModel.from_dict(message_value)
        
        # Write to DynamoDB (hot storage)
        dynamodb_success = await dynamodb_writer.write_event(event)
        if not dynamodb_success:
            logger.warning(
                "dynamodb_write_skipped",
                event_id=str(event.event_id),
                reason="event_already_exists",
            )
        
        # Write to S3 (cold storage) - graceful degradation
        s3_success = await s3_writer.write_event(event)
        if not s3_success:
            logger.warning(
                "s3_write_failed_continuing",
                event_id=str(event.event_id),
            )
            # Continue processing even if S3 fails
        
        logger.info(
            "event_processed",
            event_id=str(event.event_id),
            event_type=event.event_type,
            user_id=event.user_id,
            dynamodb_success=dynamodb_success,
            s3_success=s3_success,
        )
        
        return True
        
    except Exception as e:
        logger.error(
            "event_processing_failed",
            event_id=str(message_value.get("event_id", "unknown")),
            error=str(e),
        )
        await send_to_dlq(message_value, str(e))
        return False


async def consume_events() -> None:
    """Main consumer loop."""
    global consumer
    
    try:
        # Initialize consumer
        consumer = AIOKafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id=CONSUMER_GROUP,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            enable_auto_commit=False,  # Manual commit for at-least-once semantics
            auto_offset_reset="earliest",
        )
        
        await consumer.start()
        logger.info(
            "consumer_started",
            topic=KAFKA_TOPIC,
            consumer_group=CONSUMER_GROUP,
        )
        
        # Ensure storage resources exist
        await dynamodb_writer.ensure_table_exists()
        await s3_writer.ensure_bucket_exists()
        
        # Process messages
        async for message in consumer:
            if shutdown_event.is_set():
                logger.info("shutdown_signal_received")
                break
            
            try:
                success = await process_message(message.value)
                
                # Commit offset only after successful processing (at-least-once)
                if success:
                    await consumer.commit()
                else:
                    # Don't commit on failure - will retry
                    logger.warning(
                        "message_not_committed",
                        partition=message.partition,
                        offset=message.offset,
                    )
                    
            except Exception as e:
                logger.error(
                    "message_processing_exception",
                    partition=message.partition,
                    offset=message.offset,
                    error=str(e),
                )
                await send_to_dlq(message.value, str(e))
                # Don't commit on exception
    
    except KafkaError as e:
        logger.error("kafka_consumer_error", error=str(e))
        raise
    finally:
        if consumer:
            await consumer.stop()
            logger.info("consumer_stopped")
        if dlq_producer:
            await dlq_producer.stop()
            logger.info("dlq_producer_stopped")


def setup_signal_handlers() -> None:
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(sig, frame):
        logger.info("signal_received", signal=sig)
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main() -> None:
    """Main entry point."""
    setup_signal_handlers()
    
    try:
        await consume_events()
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received")
    except Exception as e:
        logger.error("consumer_fatal_error", error=str(e))
        raise
    finally:
        logger.info("consumer_shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())

