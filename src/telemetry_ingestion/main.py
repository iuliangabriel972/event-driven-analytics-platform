"""Telemetry Ingestion API."""
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException, status

from src.shared.logger import configure_logging, get_logger
from src.telemetry_ingestion.kafka_client import KafkaProducer
from src.telemetry_ingestion.schemas import TelemetryRequest, TelemetryResponse

configure_logging(environment=os.getenv("ENVIRONMENT", "development"))
logger = get_logger(__name__)

# Initialize Kafka producer
kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
kafka_topic = os.getenv("KAFKA_TOPIC", "vehicle-telemetry")
kafka_producer = KafkaProducer(bootstrap_servers=kafka_bootstrap, topic=kafka_topic)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle."""
    await kafka_producer.connect()
    logger.info("telemetry_api_started", port=8000)
    yield
    await kafka_producer.disconnect()
    logger.info("telemetry_api_shutdown")


app = FastAPI(
    title="Vehicle Telemetry Ingestion API",
    description="API for ingesting connected vehicle telemetry data",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "telemetry_ingestion"}


@app.post("/telemetry", response_model=TelemetryResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_telemetry(telemetry: TelemetryRequest) -> TelemetryResponse:
    """
    Ingest vehicle telemetry data.
    
    Accepts telemetry data from connected vehicles and publishes to Kafka.
    """
    telemetry_id = uuid4()
    
    # Create message with metadata
    message = {
        "telemetry_id": str(telemetry_id),
        "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
        "vehicle_id": telemetry.vehicle_id,
        "driver_id": telemetry.driver_id,
        "event_type": telemetry.event_type,
        "timestamp": telemetry.timestamp.isoformat(),
        "data": telemetry.data,
    }
    
    try:
        await kafka_producer.publish(message)
        logger.info(
            "telemetry_ingested",
            telemetry_id=str(telemetry_id),
            vehicle_id=telemetry.vehicle_id,
            driver_id=telemetry.driver_id,
            event_type=telemetry.event_type,
        )
        
        return TelemetryResponse(
            telemetry_id=telemetry_id,
            status="accepted",
            message="Telemetry data accepted for processing",
        )
    except Exception as e:
        logger.error("telemetry_ingestion_failed", telemetry_id=str(telemetry_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to process telemetry: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

