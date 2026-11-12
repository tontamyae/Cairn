from fastapi import APIRouter
from cairn.server.miner_monitor import get_miners

router = APIRouter(tags=["miners"])


@router.get("/miners")
def list_miners():
    """Read-only status for the configured LAN miners."""
    return get_miners()
