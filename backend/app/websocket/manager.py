import json
import logging
from typing import Dict, List, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, device_id: str) -> None:
        await websocket.accept()
        if device_id not in self.active_connections:
            self.active_connections[device_id] = []
        self.active_connections[device_id].append(websocket)

    def disconnect(self, websocket: WebSocket, device_id: str) -> None:
        if device_id in self.active_connections:
            try:
                self.active_connections[device_id].remove(websocket)
            except ValueError:
                pass  # Already removed — safe to ignore
            if not self.active_connections[device_id]:
                del self.active_connections[device_id]

    async def broadcast_to_device(
        self,
        device_id: str,
        message: dict,
        exclude: Optional[WebSocket] = None,
    ) -> None:
        """
        Send `message` to every socket subscribed to this device's room.

        Pass `exclude=<socket>` to skip the originating sender — this is what
        prevents a device's `wash_progress` event from being echoed straight
        back to the device that sent it.
        """
        if device_id not in self.active_connections:
            return
        dead: list[WebSocket] = []
        payload = json.dumps(message)
        for ws in list(self.active_connections[device_id]):
            if ws is exclude:
                continue
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, device_id)
            logger.warning("Removed dead WebSocket for device %s", device_id)

    async def send_to_socket(self, websocket: WebSocket, message: dict) -> None:
        await websocket.send_text(json.dumps(message))


manager = ConnectionManager()
