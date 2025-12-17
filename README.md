# Event-Driven Analytics Platform

A scalable event-driven analytics platform built with Python, Kafka (Redpanda), GraphQL, and AWS. This platform demonstrates modern microservices architecture, real-time data ingestion, and cloud-native storage patterns.

## 🏗️ Architecture

The platform consists of three main services communicating through Kafka:

```
┌─────────┐      ┌──────────────┐      ┌─────────────┐
│ Client  │─────▶│ Producer API │─────▶│   Kafka     │
│         │      │   (FastAPI)  │      │  (Redpanda) │
└─────────┘      └──────────────┘      └──────┬──────┘
                                               │
                                               ▼
                                    ┌──────────────────┐
                                    │ Consumer Service │
                                    │   (2 instances)  │
                                    └──────┬───────────┘
                                           │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
            ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
            │  DynamoDB    │      │     S3       │      │ GraphQL API  │
            │  (Hot Data)  │      │ (Cold Data)  │      │  (Read-Only) │
            └──────────────┘      └──────────────┘      └──────────────┘
```

### Data Flow

1. **Event Ingestion**: Client sends events to Producer API (`POST /events`)
2. **Event Streaming**: Producer publishes events to Kafka topic `events.raw`
3. **Event Processing**: Consumer service (2 instances) processes events with at-least-once semantics
4. **Data Storage**:
   - **Hot Storage (DynamoDB)**: Normalized event data for fast queries
   - **Cold Storage (S3)**: Raw JSON events for archival and analytics
5. **Data Querying**: GraphQL API provides read-only access to DynamoDB data

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- AWS Account (for DynamoDB and S3)
- AWS CLI configured with a profile

### Local Development

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd event-platform
   ```

2. **Configure environment**:
   ```bash
   cp env.example .env
   # Edit .env with your AWS configuration
   ```

3. **Start services**:
   ```bash
   docker-compose up -d
   ```

4. **Verify services**:
   ```bash
   # Check Producer API
   curl http://localhost:8000/health
   
   # Check GraphQL API
   curl http://localhost:8001/health
   ```

5. **Send a test event**:
   ```bash
   curl -X POST http://localhost:8000/events \
     -H "Content-Type: application/json" \
     -d '{
       "event_type": "page_view",
       "user_id": "123",
       "payload": {"page": "/home", "referrer": "google.com"}
     }'
   ```

6. **Query events via GraphQL**:
   ```bash
   curl -X POST http://localhost:8001/graphql \
     -H "Content-Type: application/json" \
     -d '{
       "query": "{ latestEvents(limit: 5) { eventId eventType userId timestamp payload } }"
     }'
   ```

### Running Without Docker

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start Redpanda** (or use existing Kafka):
   ```bash
   docker run -d -p 9092:9092 docker.redpanda.com/vectorized/redpanda:v23.2.11 redpanda start --kafka-addr internal://0.0.0.0:9092,external://0.0.0.0:19092 --advertise-kafka-addr internal://localhost:9092,external://localhost:19092 --smp 1 --memory 1G --mode dev-container
   ```

3. **Start services** (in separate terminals):
   ```bash
   # Producer
   python -m producer.main
   
   # Consumer
   python -m consumer.main
   
   # GraphQL API
   python -m graphql_api.main
   ```

## 📦 Services

### Producer API (`producer/`)

FastAPI service that accepts events via HTTP and publishes them to Kafka.

**Endpoints**:
- `POST /events` - Ingest an event
- `GET /health` - Health check

**Request Format**:
```json
{
  "event_type": "page_view",
  "user_id": "123",
  "payload": {
    "page": "/home",
    "referrer": "google.com"
  }
}
```

**Response**:
```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "accepted",
  "message": "Event accepted for processing"
}
```

### Consumer Service (`consumer/`)

Async Kafka consumer that processes events and writes to DynamoDB and S3.

**Features**:
- Consumer group: `event-processors` (enables horizontal scaling)
- At-least-once delivery semantics
- Dead letter queue for failed messages
- Idempotent writes to DynamoDB
- Graceful shutdown handling

**Storage**:
- **DynamoDB**: Normalized event data with GSI for efficient queries
- **S3**: Raw JSON events organized by date (`events/YYYY/MM/DD/{event_id}.json`)

### GraphQL API (`graphql_api/`)

Read-only GraphQL API for querying events from DynamoDB.

**Endpoint**: `POST /graphql`

**Queries**:

1. **latestEvents(limit: Int)**: Get the most recent events
   ```graphql
   {
     latestEvents(limit: 10) {
       eventId
       eventType
       userId
       timestamp
       payload
     }
   }
   ```

2. **eventsByType(eventType: String)**: Filter events by type
   ```graphql
   {
     eventsByType(eventType: "page_view") {
       eventId
       userId
       timestamp
       payload
     }
   }
   ```

3. **eventsByUser(userId: String)**: Filter events by user
   ```graphql
   {
     eventsByUser(userId: "123") {
       eventId
       eventType
       timestamp
       payload
     }
   }
   ```

## 🔧 Configuration

### Environment Variables

See `env.example` for all configuration options:

- **Kafka**: `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_TOPIC`, `KAFKA_CONSUMER_GROUP`
- **AWS**: `AWS_REGION`, `AWS_PROFILE`, `DYNAMODB_TABLE`, `S3_BUCKET`
- **Service**: `ENVIRONMENT` (development/production)

### AWS Setup

See [infra/aws.md](infra/aws.md) for detailed AWS deployment instructions.

## 📊 Kafka Consumer Groups

### How It Works

Consumer groups enable horizontal scaling of event processing:

- **Same Group**: Multiple consumers in the same group share partitions
- **Load Balancing**: Kafka automatically distributes partitions across consumers
- **Fault Tolerance**: If a consumer fails, its partitions are reassigned to other consumers

### Example

With 2 consumer instances in group `event-processors`:
- Kafka topic has 4 partitions
- Consumer 1 processes partitions 0, 1
- Consumer 2 processes partitions 2, 3
- If Consumer 1 fails, Consumer 2 takes over partitions 0, 1

### At-Least-Once Semantics

- Consumer commits offset **after** successful write to DynamoDB
- If consumer crashes before commit, message is reprocessed
- Idempotent writes prevent duplicate data in DynamoDB

## 🗄️ Hot vs Cold Storage

### Hot Storage (DynamoDB)

**Purpose**: Fast, queryable access to recent events

**Characteristics**:
- Normalized schema for efficient queries
- Global Secondary Indexes (GSI) for filtering
- Optimized for read operations
- Cost-effective for frequently accessed data

**Use Cases**:
- Real-time dashboards
- User activity tracking
- Recent event queries

### Cold Storage (S3)

**Purpose**: Long-term archival and batch analytics

**Characteristics**:
- Raw JSON format (no schema changes)
- Organized by date for efficient retrieval
- Cost-effective for large volumes
- Suitable for data lake patterns

**Use Cases**:
- Historical analysis
- Compliance and auditing
- Data science workflows
- Backup and recovery

## 🚢 AWS Deployment

See [infra/aws.md](infra/aws.md) for complete deployment guide.

### Free Tier Considerations

- **DynamoDB**: 25 GB storage, 25 read/write units
- **S3**: 5 GB storage, 20,000 GET requests
- **EC2**: t2.micro instance (if needed)

### Quick AWS Setup

1. Create S3 bucket:
   ```bash
   aws s3 mb s3://event-platform-raw-events --region us-east-1
   ```

2. Configure IAM permissions (see `infra/aws.md`)

3. Update `.env` with AWS credentials

4. Deploy:
   ```bash
   docker-compose up -d
   ```

## 🧪 Testing

### Manual Testing

1. **Send events**:
   ```bash
   for i in {1..10}; do
     curl -X POST http://localhost:8000/events \
       -H "Content-Type: application/json" \
       -d "{\"event_type\": \"page_view\", \"user_id\": \"user$i\", \"payload\": {\"page\": \"/page$i\"}}"
   done
   ```

2. **Query via GraphQL**:
   ```bash
   curl -X POST http://localhost:8001/graphql \
     -H "Content-Type: application/json" \
     -d '{"query": "{ latestEvents(limit: 10) { eventId eventType userId } }"}'
   ```

3. **Check DynamoDB**:
   ```bash
   aws dynamodb scan --table-name EventsHot --limit 5
   ```

4. **Check S3**:
   ```bash
   aws s3 ls s3://event-platform-raw-events/events/ --recursive
   ```

## 📈 Scalability Model

### Horizontal Scaling

- **Producer**: Stateless, scale by adding instances behind load balancer
- **Consumer**: Scale by adding more instances to consumer group
- **GraphQL API**: Stateless, scale by adding instances

### Vertical Scaling

- **Kafka/Redpanda**: Increase partitions for higher throughput
- **DynamoDB**: Adjust read/write capacity or use on-demand
- **S3**: Automatically scales

### Performance Considerations

- **Kafka Partitions**: More partitions = more parallelism
- **Consumer Instances**: Should not exceed partition count
- **DynamoDB GSI**: Enables efficient filtering without full table scans
- **S3 Batching**: Consider batching writes for high-volume scenarios

## 🛡️ Error Handling

### Dead Letter Queue (DLQ)

Failed messages are sent to `events.dlq` topic with error metadata:
- Original message preserved
- Error details included
- Timestamp of failure
- Can be reprocessed later

### Idempotency

- DynamoDB writes check for existing events
- Prevents duplicate data from retries
- Uses `event_id` + `timestamp` as composite key

### Graceful Degradation

- S3 write failures don't block processing
- Consumer continues even if one storage backend fails
- Errors logged for monitoring

## 🔍 Monitoring

### Logs

All services use structured logging:
- **Development**: Colored console output
- **Production**: JSON format for log aggregation

### Key Metrics to Monitor

- **Producer**: Event ingestion rate, Kafka publish latency
- **Consumer**: Processing rate, consumer lag, error rate
- **GraphQL**: Query latency, error rate
- **DynamoDB**: Read/write capacity, throttling
- **S3**: Request count, storage usage

## 🎯 Trade-offs and Future Improvements

### Current Trade-offs

1. **At-Least-Once**: Simpler than exactly-once, acceptable for analytics
2. **Scan for Latest Events**: Not optimal for large tables (consider time-based partitioning)
3. **Single Kafka Topic**: Could partition by event type for better isolation
4. **No Authentication**: Add API keys/JWT for production

### Future Improvements

1. **Exactly-Once Semantics**: Use Kafka transactions for critical events
2. **Event Schema Registry**: Validate event schemas
3. **Caching Layer**: Redis for frequently accessed events
4. **Stream Processing**: Add Kafka Streams or Flink for real-time aggregations
5. **Monitoring**: Integrate Prometheus/Grafana
6. **API Authentication**: OAuth2/JWT for secure access
7. **Event Replay**: Ability to reprocess events from S3
8. **Multi-Region**: Deploy across AWS regions for disaster recovery
9. **Data Retention**: TTL policies for DynamoDB, lifecycle policies for S3
10. **GraphQL Subscriptions**: Real-time event streaming via WebSockets

## 📚 Technology Stack

- **Python 3.11**: Modern Python with async/await
- **FastAPI**: High-performance async web framework
- **Strawberry GraphQL**: Type-safe GraphQL implementation
- **Redpanda**: Kafka-compatible message broker (lighter than Kafka)
- **aiokafka**: Async Kafka client
- **DynamoDB**: NoSQL database for hot storage
- **S3**: Object storage for cold storage
- **boto3/aioboto3**: AWS SDK for Python
- **Docker**: Containerization
- **structlog**: Structured logging

## 📝 License

This project is a demonstration/portfolio piece.

## 🤝 Contributing

This is a demo project, but suggestions and improvements are welcome!

---

**Built for demonstrating event-driven architecture, microservices, and cloud-native patterns.**
