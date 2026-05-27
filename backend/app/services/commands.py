import json
import logging

from sqlalchemy.orm import Session

from app.models.pending_command import PendingCommand
from app.websocket.manager import manager

logger = logging.getLogger(__name__)


async def dispatch_command(db: Session, device_id: int, payload: dict) -> None:
    """
    Send a command to a device via BOTH transports:
      - Enqueue a row in `pending_commands` so HTTP-polling devices pick it up.
      - Broadcast over WebSocket so any connected listener gets it immediately.

    A device should use one transport or the other — not both — but the server
    publishes to both so firmware choice is transparent.
    """
    pending = PendingCommand(
        device_id=device_id,
        command=str(payload.get("command", "")),
        payload=json.dumps(payload),
    )
    db.add(pending)
    db.commit()

    await manager.broadcast_to_device(str(device_id), payload)
