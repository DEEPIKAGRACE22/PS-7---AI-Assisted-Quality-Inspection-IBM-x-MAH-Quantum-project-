"""Unit tests for WebSocket real-time updates.
Tests connection establishment, subscription, keepalive ping/pong, and message reception.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_websocket_inspection_subscription():
    with client.websocket_connect("/ws/inspections/test-inspection-123") as ws:
        # Receive welcome / connected event
        data = ws.receive_text()
        msg = json.loads(data)
        assert msg["event"] == "connected"
        assert msg["inspection_id"] == "test-inspection-123"

        # Send ping and receive pong
        ws.send_text("ping")
        pong = ws.receive_text()
        assert pong == "pong"


def test_websocket_global_feed():
    with client.websocket_connect("/ws/inspections") as ws:
        data = ws.receive_text()
        msg = json.loads(data)
        assert msg["event"] == "connected"
        assert msg["inspection_id"] == "all"

        ws.send_text("ping")
        assert ws.receive_text() == "pong"


if __name__ == "__main__":
    print("Running WebSocket test suite...")
    test_websocket_inspection_subscription()
    print("-> test_websocket_inspection_subscription: PASSED")
    test_websocket_global_feed()
    print("-> test_websocket_global_feed: PASSED")
    print("ALL WEBSOCKET TESTS PASSED!")
