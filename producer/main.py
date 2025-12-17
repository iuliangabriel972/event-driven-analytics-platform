"""Producer API service for ingesting events."""
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

from producer.kafka import KafkaProducer
from producer.schemas import EventEnvelope, EventRequest, EventResponse
from shared.logger import configure_logging, get_logger

# Configure logging
configure_logging(environment=os.getenv("ENVIRONMENT", "development"))
logger = get_logger(__name__)

# Initialize Kafka producer
kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
kafka_topic = os.getenv("KAFKA_TOPIC", "events.raw")
kafka_producer = KafkaProducer(bootstrap_servers=kafka_bootstrap, topic=kafka_topic)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    try:
        await kafka_producer.connect()
        logger.info("producer_service_started", port=8000)
    except Exception as e:
        logger.error("producer_service_startup_failed", error=str(e))
        raise
    
    yield
    
    # Shutdown
    await kafka_producer.disconnect()
    logger.info("producer_service_shutdown")


app = FastAPI(
    title="Event Producer API",
    description="API for ingesting events into the analytics platform",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "producer"}


@app.post("/events", response_model=EventResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(event: EventRequest) -> EventResponse:
    """
    Ingest an event into the platform.
    
    Accepts event data, adds metadata (event_id, timestamp), and publishes to Kafka.
    
    Args:
        event: Event request data
        
    Returns:
        EventResponse with event_id and status
        
    Raises:
        HTTPException: If event publishing fails
    """
    # Generate metadata
    event_id = uuid4()
    timestamp = datetime.now(timezone.utc)
    
    # Create event envelope
    event_envelope = EventEnvelope(
        event_id=event_id,
        timestamp=timestamp,
        event_type=event.event_type,
        user_id=event.user_id,
        payload=event.payload,
    )
    
    # Publish to Kafka
    try:
        await kafka_producer.publish(event_envelope.model_dump(mode="json"))
        logger.info(
            "event_ingested",
            event_id=str(event_id),
            event_type=event.event_type,
            user_id=event.user_id,
        )
        
        return EventResponse(
            event_id=event_id,
            status="accepted",
            message="Event accepted for processing",
        )
    except Exception as e:
        logger.error(
            "event_ingestion_failed",
            event_id=str(event_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to publish event: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

