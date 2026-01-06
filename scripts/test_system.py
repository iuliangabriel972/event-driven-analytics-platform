#!/usr/bin/env python3
"""
Simple test script to send events and query them via GraphQL.

Usage:
    python scripts/test_system.py send           # Send 5 test events
    python scripts/test_system.py query          # Query latest events
    python scripts/test_system.py test           # Send events then query
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4

# Fix Windows console encoding for emoji support
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

import requests
from jose import jwt

# Configuration
ALB_DNS = "event-platform-alb-95530675.us-east-1.elb.amazonaws.com"
TELEMETRY_API_URL = f"http://{ALB_DNS}:8000"
GRAPHQL_API_URL = f"http://{ALB_DNS}:8001/graphql"
JWT_SECRET = "change-me-in-production-use-secrets-manager"
JWT_ALGORITHM = "HS256"


def generate_jwt_token():
    """Generate a JWT token for authentication."""
    payload = {
        "sub": "test-user",
        "aud": "event-platform",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc).timestamp() + 3600,  # 1 hour
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def send_events(count=5):
    """Send test events to the Telemetry API."""
    print(f"\n🚀 Sending {count} test events to {TELEMETRY_API_URL}")
    print("=" * 60)
    
    # Generate JWT token
    token = generate_jwt_token()
    print(f"✅ JWT token generated\n")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    successful = 0
    failed = 0
    
    for i in range(1, count + 1):
        event = {
            "event_id": str(uuid4()),
            "event_type": "user.action",
            "user_id": f"user-{i % 3 + 1}",  # Rotate between 3 users
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "action": ["login", "purchase", "view_product", "add_to_cart", "logout"][i % 5],
                "amount": round(10.5 * i, 2),
                "count": i,
                "metadata": {
                    "ip": f"192.168.1.{i}",
                    "user_agent": "test-client/1.0"
                }
            }
        }
        
        try:
            response = requests.post(
                f"{TELEMETRY_API_URL}/events",
                headers=headers,
                json=event,
                timeout=10
            )
            
            if response.status_code in (200, 201, 202):
                result = response.json()
                print(f"  [{i}/{count}] ✅ Event sent: {result.get('event_id', 'N/A')}")
                successful += 1
            else:
                print(f"  [{i}/{count}] ❌ Failed: {response.status_code} - {response.text}")
                failed += 1
        except requests.exceptions.Timeout:
            print(f"  [{i}/{count}] ⏱️  Timeout (API might be slow)")
            failed += 1
        except Exception as e:
            print(f"  [{i}/{count}] ❌ Error: {str(e)}")
            failed += 1
        
        # Small delay between requests
        if i < count:
            time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print(f"📊 Results: {successful} successful, {failed} failed")
    
    if successful > 0:
        print("\n⏳ Waiting 10 seconds for events to be processed...")
        time.sleep(10)
    
    return successful, failed


def query_events(limit=10):
    """Query events via GraphQL."""
    print(f"\n🔍 Querying latest {limit} events from {GRAPHQL_API_URL}")
    print("=" * 60)
    
    # Generate JWT token
    token = generate_jwt_token()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    query = {
        "query": f"""
        query {{
            latestEvents(limit: {limit}) {{
                eventId
                eventType
                userId
                timestamp
                payload
            }}
        }}
        """
    }
    
    try:
        response = requests.post(
            GRAPHQL_API_URL,
            headers=headers,
            json=query,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if "errors" in result:
                print(f"❌ GraphQL errors: {result['errors']}")
                return False
            
            events = result.get("data", {}).get("latestEvents", [])
            
            if not events:
                print("⚠️  No events found in database")
                return False
            
            print(f"✅ Found {len(events)} events\n")
            
            for i, event in enumerate(events, 1):
                print(f"  Event {i}:")
                print(f"    ID: {event['eventId']}")
                print(f"    Type: {event['eventType']}")
                print(f"    User: {event['userId']}")
                print(f"    Time: {event['timestamp']}")
                
                # Parse and display payload
                try:
                    payload = json.loads(event['payload'])
                    print(f"    Payload: {json.dumps(payload, indent=6)}")
                except:
                    print(f"    Payload: {event['payload']}")
                print()
            
            return True
        else:
            print(f"❌ HTTP {response.status_code}: {response.text}")
            return False
    
    except requests.exceptions.Timeout:
        print("⏱️  Query timeout - API might be slow or down")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_health():
    """Check API health endpoints."""
    print("\n🏥 Checking API health")
    print("=" * 60)
    
    # Check Telemetry API
    try:
        response = requests.get(f"{TELEMETRY_API_URL}/health", timeout=5)
        if response.status_code == 200:
            print(f"✅ Telemetry API: {response.json()}")
        else:
            print(f"⚠️  Telemetry API: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Telemetry API: {str(e)}")
    
    # Check GraphQL API
    try:
        response = requests.get(f"http://{ALB_DNS}:8001/health", timeout=5)
        if response.status_code == 200:
            print(f"✅ GraphQL API: {response.json()}")
        else:
            print(f"⚠️  GraphQL API: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ GraphQL API: {str(e)}")


def main():
    parser = argparse.ArgumentParser(
        description="Test the event-driven analytics platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/test_system.py send              # Send 5 events
  python scripts/test_system.py send --count 10   # Send 10 events
  python scripts/test_system.py query             # Query latest events
  python scripts/test_system.py query --limit 20  # Query 20 events
  python scripts/test_system.py test              # Full test (send + query)
  python scripts/test_system.py health            # Check API health
        """
    )
    
    parser.add_argument(
        "action",
        choices=["send", "query", "test", "health"],
        help="Action to perform"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of events to send (default: 5)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of events to query (default: 10)"
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("  EVENT-DRIVEN ANALYTICS PLATFORM - SYSTEM TEST")
    print("=" * 60)
    
    if args.action == "health":
        test_health()
    
    elif args.action == "send":
        successful, failed = send_events(args.count)
        sys.exit(0 if failed == 0 else 1)
    
    elif args.action == "query":
        success = query_events(args.limit)
        sys.exit(0 if success else 1)
    
    elif args.action == "test":
        # Full test: health check, send events, then query
        test_health()
        successful, failed = send_events(args.count)
        
        if successful > 0:
            success = query_events(args.limit)
            
            if success:
                print("\n" + "=" * 60)
                print("✅✅✅ FULL SYSTEM TEST PASSED!")
                print("=" * 60)
                sys.exit(0)
            else:
                print("\n❌ Query failed")
                sys.exit(1)
        else:
            print("\n❌ No events sent successfully")
            sys.exit(1)
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

