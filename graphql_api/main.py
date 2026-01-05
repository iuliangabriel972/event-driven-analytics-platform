"""GraphQL API service for querying events."""
import os

from fastapi import Depends, FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from strawberry.fastapi import GraphQLRouter

from graphql_api.schema import schema
from shared.auth import get_current_user
from shared.logger import configure_logging, get_logger

# Configure logging
configure_logging(environment=os.getenv("ENVIRONMENT", "development"))
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Event GraphQL API",
    description="Read-only GraphQL API for querying events",
    version="1.0.0",
)

# Instrument with Prometheus BEFORE adding routes
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app, include_in_schema=False)

# Create GraphQL router
graphql_app = GraphQLRouter(
    schema,
    prefix="/graphql",
    dependencies=[Depends(get_current_user)],
)

# Mount GraphQL endpoint
app.include_router(graphql_app)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Event GraphQL API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "graphql": "/graphql",
            "metrics": "/metrics"
        },
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "graphql_api"}


@app.on_event("startup")
async def startup_event():
    """Service startup hook."""
    logger.info("graphql_api_service_started", port=8001)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)

