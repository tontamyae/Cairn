from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from cairn.server.db import get_conn
from cairn.server.models import CommandApproval, CommandApprovalCreate

router = APIRouter(tags=["command-approvals"])


def now_utc():
    return datetime.now(timezone.utc)


@router.post("/command-approvals", response_model=CommandApproval)
def create_approval(body: CommandApprovalCreate):
    now = now_utc()
    item = {
        "id": str(uuid4()),
        "command": body.command,
        "working_directory": body.working_directory,
        "status": "pending",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "decided_at": None,
        "decision_note": None,
    }
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO command_approvals
            (id, command, working_directory, status, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (item["id"], item["command"], item["working_directory"],
             item["status"], item["created_at"], item["expires_at"]),
        )
    return item


@router.get("/command-approvals", response_model=list[CommandApproval])
def list_approvals():
    now = now_utc().isoformat()
    with get_conn() as conn:
        conn.execute(
            """UPDATE command_approvals SET status = 'expired'
            WHERE status = 'pending' AND expires_at <= ?""",
            (now,),
        )
        rows = conn.execute(
            "SELECT * FROM command_approvals ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
        return [dict(row) for row in rows]


def decide(approval_id: str, status: str):
    now = now_utc().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM command_approvals WHERE id = ?", (approval_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Approval not found")
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail="Approval is not pending")
        if row["expires_at"] <= now:
            conn.execute(
                "UPDATE command_approvals SET status = 'expired' WHERE id = ?",
                (approval_id,),
            )
            raise HTTPException(status_code=409, detail="Approval expired")
        conn.execute(
            "UPDATE command_approvals SET status = ?, decided_at = ? WHERE id = ?",
            (status, now, approval_id),
        )
        updated = conn.execute(
            "SELECT * FROM command_approvals WHERE id = ?", (approval_id,)
        ).fetchone()
        return dict(updated)


@router.post("/command-approvals/{approval_id}/approve",
             response_model=CommandApproval)
def approve_approval(approval_id: str):
    return decide(approval_id, "approved")


@router.post("/command-approvals/{approval_id}/reject",
             response_model=CommandApproval)
def reject_approval(approval_id: str):
    return decide(approval_id, "rejected")
