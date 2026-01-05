"""Kafka producer client for publishing events."""
import json
from typing import Optional

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from shared.logger import get_logger

logger = get_logger(__name__)


class KafkaProducer:
    """Async Kafka producer for publishing events."""
    
    def __init__(self, bootstrap_servers: str, topic: str = "events.raw"):
        """
        Initialize Kafka producer.
        
        Args:
            bootstrap_servers: Kafka broker address (e.g., 'localhost:9092')
            topic: Topic name to publish events to
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer: Optional[AIOKafkaProducer] = None
    
    async def connect(self) -> None:
        """Connect to Kafka broker."""
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                retry_backoff_ms=100,
                request_timeout_ms=60000,  # 60 seconds timeout
                api_version='auto',
            )
            await self.producer.start()
            logger.info("kafka_producer_connected", bootstrap_servers=self.bootstrap_servers, topic=self.topic)
        except Exception as e:
            logger.error("kafka_producer_connection_failed", error=str(e), bootstrap_servers=self.bootstrap_servers)
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Kafka broker."""
        if self.producer:
            try:
                await self.producer.stop()
                logger.info("kafka_producer_disconnected")
            except Exception as e:
                logger.error("kafka_producer_disconnect_error", error=str(e))
    
    async def publish(self, event: dict) -> None:
        """
        Publish event to Kafka topic.
        
        Args:
            event: Event dictionary to publish
            
        Raises:
            KafkaError: If publishing fails
        """
        if not self.producer:
            # Try to connect if not already connected
            try:
                await self.connect()
            except Exception as e:
                logger.error("kafka_auto_connect_failed", error=str(e))
                raise RuntimeError(f"Producer not connected and auto-connect failed: {str(e)}")
        
        try:
            await self.producer.send_and_wait(self.topic, event)
            logger.info(
                "event_published",
                event_id=str(event.get("event_id")),
                event_type=event.get("event_type"),
                topic=self.topic,
            )
        except KafkaError as e:
            logger.error(
                "event_publish_failed",
                event_id=str(event.get("event_id")),
                error=str(e),
                topic=self.topic,
            )
            raise

