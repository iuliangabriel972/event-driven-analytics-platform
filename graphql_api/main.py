"""GraphQL API service for querying events."""
import os

from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from graphql_api.schema import schema
from shared.logger import configure_logging, get_logger

# Configure logging
configure_logging(environment=os.getenv("ENVIRONMENT", "development"))
logger = get_logger(__name__)

# Create GraphQL router
graphql_app = GraphQLRouter(schema)

# Create FastAPI app
app = FastAPI(
    title="Event GraphQL API",
    description="Read-only GraphQL API for querying events",
    version="1.0.0",
)

# Mount GraphQL endpoint
app.include_router(graphql_app, prefix="/graphql")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "graphql_api"}


@app.on_event("startup")
async def startup_event():
    """Log service startup."""
    logger.info("graphql_api_service_started", port=8001)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

