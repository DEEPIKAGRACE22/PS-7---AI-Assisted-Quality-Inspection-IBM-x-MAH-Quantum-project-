"""WebSocket API endpoints.
Provides real-time streaming updates for video frame processing, defect alerts,
and live inspection feeds.
"""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSockets"])


@router.websocket("/ws/inspections/{inspection_id}")
async def websocket_inspection_endpoint(websocket: WebSocket, inspection_id: str):
    """WebSocket endpoint for monitoring a specific inspection in real time."""
    await ws_manager.connect(websocket, inspection_id=inspection_id)
    try:
        # Send initial connection confirmation
        await websocket.send_text(json.dumps({
            "event": "connected",
            "inspection_id": inspection_id,
            "message": f"Successfully subscribed to inspection '{inspection_id}' stream.",
        }))
        while True:
            # Keep socket alive and respond to client ping/messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, inspection_id=inspection_id)
    except Exception as e:
        logger.debug(f"WebSocket error on inspection '{inspection_id}': {e}")
        ws_manager.disconnect(websocket, inspection_id=inspection_id)


@router.websocket("/ws/inspections")
async def websocket_global_feed_endpoint(websocket: WebSocket):
    """WebSocket endpoint for global plant floor live inspection stream."""
    await ws_manager.connect(websocket, inspection_id="all")
    try:
        await websocket.send_text(json.dumps({
            "event": "connected",
            "inspection_id": "all",
            "message": "Connected to global industrial inspection feed.",
        }))
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, inspection_id="all")
    except Exception as e:
        logger.debug(f"WebSocket global error: {e}")
        ws_manager.disconnect(websocket, inspection_id="all")
