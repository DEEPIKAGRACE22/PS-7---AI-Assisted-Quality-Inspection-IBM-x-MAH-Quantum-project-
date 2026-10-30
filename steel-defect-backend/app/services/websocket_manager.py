"""WebSocket connection manager for real-time video processing updates and alerts.
Industrial AI Steel Surface Defect Detection Platform.
"""

import asyncio
import json
import logging
from typing import Dict, Set, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """Manages active WebSocket connections for live inspection streaming."""

    def __init__(self):
        # Map inspection_id -> Set of WebSockets
        self.inspection_rooms: Dict[str, Set[WebSocket]] = {}
        # Global listeners (dashboard live feed)
        self.global_listeners: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, inspection_id: str = "all") -> None:
        """Accept WebSocket connection and register in the requested room."""
        await websocket.accept()
        if inspection_id == "all":
            self.global_listeners.add(websocket)
            logger.info(f"WebSocket client connected to global inspection feed. Total: {len(self.global_listeners)}")
        else:
            if inspection_id not in self.inspection_rooms:
                self.inspection_rooms[inspection_id] = set()
            self.inspection_rooms[inspection_id].add(websocket)
            logger.info(
                f"WebSocket client connected to inspection '{inspection_id}'. Total: {len(self.inspection_rooms[inspection_id])}"
            )

    def disconnect(self, websocket: WebSocket, inspection_id: str = "all") -> None:
        """Remove WebSocket connection on client departure or error."""
        if inspection_id == "all":
            self.global_listeners.discard(websocket)
            logger.info(f"WebSocket client disconnected from global feed. Remaining: {len(self.global_listeners)}")
        else:
            if inspection_id in self.inspection_rooms:
                self.inspection_rooms[inspection_id].discard(websocket)
                if not self.inspection_rooms[inspection_id]:
                    del self.inspection_rooms[inspection_id]
            logger.info(f"WebSocket client disconnected from inspection '{inspection_id}'.")

    async def broadcast_inspection_event(self, inspection_id: str, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcast an event payload to both room subscribers and global feed listeners."""
        payload = json.dumps({
            "event": event_type,
            "inspection_id": inspection_id,
            "data": data,
        })

        targets: Set[WebSocket] = set(self.global_listeners)
        if inspection_id in self.inspection_rooms:
            targets.update(self.inspection_rooms[inspection_id])

        disconnected = []
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception as e:
                logger.debug(f"Failed to send to websocket: {e}")
                disconnected.append(ws)

        # Cleanup failed sockets
        for dead_ws in disconnected:
            self.global_listeners.discard(dead_ws)
            if inspection_id in self.inspection_rooms:
                self.inspection_rooms[inspection_id].discard(dead_ws)


# Global singleton instance
ws_manager = WebSocketConnectionManager()
