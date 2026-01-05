"""Analytics API service."""
import os

from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from src.analytics_api.schema import schema
from src.shared.logger import configure_logging, get_logger

configure_logging(environment=os.getenv("ENVIRONMENT", "development"))
logger = get_logger(__name__)

graphql_app = GraphQLRouter(schema)

app = FastAPI(
    title="Vehicle Telemetry Analytics API",
    description="GraphQL API for querying vehicle telemetry and driving behavior data",
    version="1.0.0",
)

app.include_router(graphql_app, prefix="/graphql")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "analytics_api"}


@app.on_event("startup")
async def startup_event():
    """Log service startup."""
    logger.info("analytics_api_started", port=8001)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

