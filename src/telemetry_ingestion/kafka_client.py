"""Kafka producer client."""
import json
from typing import Optional

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from src.shared.logger import get_logger

logger = get_logger(__name__)


class KafkaProducer:
    """Async Kafka producer."""
    
    def __init__(self, bootstrap_servers: str, topic: str):
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
            )
            await self.producer.start()
            logger.info("kafka_connected", bootstrap_servers=self.bootstrap_servers, topic=self.topic)
        except Exception as e:
            logger.error("kafka_connection_failed", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Kafka."""
        if self.producer:
            await self.producer.stop()
            logger.info("kafka_disconnected")
    
    async def publish(self, message: dict) -> None:
        """Publish message to Kafka topic."""
        if not self.producer:
            raise RuntimeError("Producer not connected")
        
        try:
            await self.producer.send_and_wait(self.topic, message)
            logger.info("message_published", topic=self.topic, vehicle_id=message.get("vehicle_id"))
        except KafkaError as e:
            logger.error("publish_failed", error=str(e))
            raise

