#!/usr/bin/env python3
"""Full end-to-end test script for the event platform."""
import json
import time
import requests
from datetime import datetime, timedelta, timezone
from jose import jwt

# Configuration
ALB_DNS = "event-platform-alb-95530675.us-east-1.elb.amazonaws.com"
TELEMETRY_URL = f"http://{ALB_DNS}:8000"
GRAPHQL_URL = f"http://{ALB_DNS}:8001/graphql"

# JWT Configuration
JWT_SECRET = "change-me-in-production-use-secrets-manager"
JWT_AUDIENCE = "event-platform"


def generate_jwt_token(subject: str = "test-user", expiration_minutes: int = 60) -> str:
    """Generate a JWT token for authentication."""
    payload = {
        "sub": subject,
        "aud": JWT_AUDIENCE,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=expiration_minutes)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def test_telemetry_health():
    """Test Telemetry API health endpoint."""
    print("1. Testing Telemetry API health...")
    try:
        response = requests.get(f"{TELEMETRY_URL}/health", timeout=10)
        response.raise_for_status()
        print(f"   [OK] Health check OK: {response.json()}")
        return True
    except Exception as e:
        print(f"   [FAIL] Health check failed: {e}")
        return False


def send_event(token: str, event_type: str, user_id: str, payload: dict) -> dict:
    """Send an event to the Telemetry API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    event = {
        "event_type": event_type,
        "user_id": user_id,
        "payload": payload,
    }
    response = requests.post(
        f"{TELEMETRY_URL}/events",
        headers=headers,
        json=event,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def query_graphql(token: str, query: str) -> dict:
    """Query the GraphQL API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"query": query}
    response = requests.post(
        GRAPHQL_URL,
        headers=headers,
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def main():
    """Run full end-to-end test."""
    print("=== FULL END-TO-END TEST ===\n")
    
    # Generate JWT token
    print("Generating JWT token...")
    token = generate_jwt_token()
    print(f"Token generated: {token[:20]}...\n")
    
    # Test health
    if not test_telemetry_health():
        print("[FAIL] Health check failed, aborting test")
        return
    
    # Check initial state
    print("\n2. Checking initial state - querying GraphQL...")
    try:
        result = query_graphql(token, "query { latestEvents(limit: 5) { eventId eventType userId } }")
        initial_count = len(result.get("data", {}).get("latestEvents", []))
        print(f"   Initial events count: {initial_count}")
    except Exception as e:
        print(f"   [WARN] GraphQL query failed: {e}")
        initial_count = 0
    
    # Send test events
    print("\n3. Sending 10 test events...")
    sent_event_ids = []
    for i in range(1, 11):
        try:
            payload = {
                "number": i,
                "message": f"Test event {i}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            response = send_event(
                token,
                event_type="test.event",
                user_id=f"test-user-{i}",
                payload=payload,
            )
            event_id = response.get("event_id")
            print(f"   [OK] Event {i} sent: {event_id}")
            sent_event_ids.append(event_id)
            time.sleep(2)  # Wait 2 seconds between events
        except Exception as e:
            print(f"   [FAIL] Event {i} failed: {e}")
    
    print(f"\n[OK] Sent {len(sent_event_ids)}/10 events successfully")
    
    # Wait for processing
    print("\n4. Waiting 60 seconds for events to be processed...")
    time.sleep(60)
    
    # Query GraphQL to retrieve events
    print("\n5. Querying GraphQL to retrieve events...")
    try:
        query = """
        query {
            latestEvents(limit: 15) {
                eventId
                eventType
                userId
                timestamp
                payload
            }
        }
        """
        result = query_graphql(token, query)
        events = result.get("data", {}).get("latestEvents", [])
        print(f"   [OK] GraphQL query successful!")
        print(f"   Found {len(events)} events in GraphQL")
        
        if events:
            print("\n   Retrieved events:")
            for event in events[:10]:  # Show first 10
                print(f"     [OK] Event ID: {event.get('eventId')}")
                print(f"        Type: {event.get('eventType')}")
                print(f"        User: {event.get('userId')}")
                print(f"        Timestamp: {event.get('timestamp')}")
                print()
        
        # Verify we got the events we sent
        retrieved_ids = {e.get("eventId") for e in events}
        sent_set = set(sent_event_ids)
        matched = sent_set.intersection(retrieved_ids)
        print(f"\n   Verification: {len(matched)}/{len(sent_event_ids)} sent events found in GraphQL")
        
        if len(matched) == len(sent_event_ids):
            print("   [SUCCESS] ALL EVENTS RETRIEVED SUCCESSFULLY!")
        else:
            print(f"   [WARN] Some events not yet processed (found {len(matched)}, sent {len(sent_event_ids)})")
            
    except Exception as e:
        print(f"   [FAIL] GraphQL query failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== TEST COMPLETE ===")


if __name__ == "__main__":
    main()

