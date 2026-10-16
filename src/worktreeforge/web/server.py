"""FastAPI server and REST API for WorktreeForge Web Studio."""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from worktreeforge import __version__
from worktreeforge.core.git_client import GitError
from worktreeforge.core.models import (
    PortAllocation,
    StashDiff,
    StashEntry,
    WorktreeInfo,
)
from worktreeforge.core.supervisor import SupervisorError, WorktreeSupervisor
from worktreeforge.multiplexer.port_allocator import is_port_available

app = FastAPI(
    title="WorktreeForge Web Studio",
    description="High-Speed Git Worktree Supervisor, Stash Studio & Local Port Multiplexer API",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"


class ConnectionManager:
    """Manages active WebSocket connections for live notifications."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


ws_manager = ConnectionManager()
_supervisor_instance: Optional[WorktreeSupervisor] = None


def get_supervisor() -> WorktreeSupervisor:
    global _supervisor_instance
    if _supervisor_instance is None:
        _supervisor_instance = WorktreeSupervisor()
    return _supervisor_instance


# -----------------------------------------------------------------------------
# Request Schemas
# -----------------------------------------------------------------------------


class CreateWorktreeRequest(BaseModel):
    branch: str
    base_ref: Optional[str] = None
    path: Optional[str] = None
    port_offset: Optional[int] = None
    configure_ports: bool = True
    open_editor: bool = False


class RemoveWorktreeRequest(BaseModel):
    identifier: str
    force: bool = False
    delete_branch: bool = False


class LockWorktreeRequest(BaseModel):
    identifier: str
    reason: Optional[str] = None


class UnlockWorktreeRequest(BaseModel):
    identifier: str


class PruneWorktreeRequest(BaseModel):
    dry_run: bool = False


class OpenEditorRequest(BaseModel):
    path: str


class ApplyStashRequest(BaseModel):
    drop: bool = False


# -----------------------------------------------------------------------------
# REST Endpoints
# -----------------------------------------------------------------------------


@app.get("/api/status")
def get_system_status():
    sup = get_supervisor()
    worktrees = sup.list_worktrees(enrich_ports=True, enrich_pr=False)
    allocations = sup.port_allocator.list_all_allocations()
    stashes = sup.stash_inspector.list_all()

    return {
        "version": __version__,
        "repo_name": sup.repo_root.name,
        "repo_path": str(sup.repo_root),
        "total_worktrees": len(worktrees),
        "total_allocations": len(allocations),
        "total_stashes": len(stashes),
    }


@app.get("/api/worktrees", response_model=List[WorktreeInfo])
def list_worktrees():
    sup = get_supervisor()
    try:
        return sup.list_worktrees(enrich_ports=True, enrich_pr=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/worktrees")
async def create_worktree(req: CreateWorktreeRequest):
    sup = get_supervisor()
    target_path = Path(req.path).resolve() if req.path else None
    try:
        wt, allocations = sup.create_worktree(
            branch=req.branch,
            base_ref=req.base_ref,
            target_path=target_path,
            port_offset=req.port_offset,
            configure_ports=req.configure_ports,
        )
        if req.open_editor:
            sup.open_editor(Path(wt.path))

        await ws_manager.broadcast({"event": "worktree_created", "branch": wt.branch})
        return {"worktree": wt, "allocations": allocations}
    except (SupervisorError, GitError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/worktrees")
async def remove_worktree(req: RemoveWorktreeRequest):
    sup = get_supervisor()
    try:
        wt, released = sup.remove_worktree(
            identifier=req.identifier,
            force=req.force,
            delete_branch=req.delete_branch,
        )
        await ws_manager.broadcast({"event": "worktree_removed", "branch": wt.branch})
        return {"worktree": wt, "released_ports": released}
    except (SupervisorError, GitError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/worktrees/lock")
async def lock_worktree(req: LockWorktreeRequest):
    sup = get_supervisor()
    try:
        wt = sup.lock_worktree(req.identifier, reason=req.reason)
        await ws_manager.broadcast({"event": "worktree_locked", "branch": wt.branch})
        return {"worktree": wt}
    except (SupervisorError, GitError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/worktrees/unlock")
async def unlock_worktree(req: UnlockWorktreeRequest):
    sup = get_supervisor()
    try:
        wt = sup.unlock_worktree(req.identifier)
        await ws_manager.broadcast({"event": "worktree_unlocked", "branch": wt.branch})
        return {"worktree": wt}
    except (SupervisorError, GitError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/worktrees/prune")
async def prune_merged(req: PruneWorktreeRequest):
    sup = get_supervisor()
    try:
        results = sup.prune_merged_worktrees(dry_run=req.dry_run)
        await ws_manager.broadcast({"event": "worktrees_pruned"})
        return [
            {"worktree": wt, "success": ok, "message": msg} for wt, ok, msg in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/worktrees/open-editor")
def open_in_editor(req: OpenEditorRequest):
    sup = get_supervisor()
    target_path = Path(req.path)
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Directory not found")
    launched = sup.open_editor(target_path)
    return {"success": launched}


@app.get("/api/ports")
def get_ports(check: bool = True):
    sup = get_supervisor()
    allocations = sup.port_allocator.list_all_allocations()
    results = []
    for a in allocations:
        is_free = is_port_available(a.allocated_port) if check else True
        results.append(
            {
                **a.model_dump(),
                "is_socket_listening": not is_free,
            }
        )
    return results


@app.get("/api/stashes", response_model=List[StashEntry])
def list_stashes():
    sup = get_supervisor()
    return sup.stash_inspector.list_all()


@app.get("/api/stashes/{index}/diff", response_model=StashDiff)
def get_stash_diff(index: int):
    sup = get_supervisor()
    try:
        return sup.stash_inspector.get_diff(index)
    except GitError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/stashes/search")
def search_stashes(q: str):
    sup = get_supervisor()
    results = sup.stash_inspector.search(q)
    return [{"stash": s, "matches": m} for s, m in results]


@app.post("/api/stashes/{index}/apply")
async def apply_stash(index: int, req: ApplyStashRequest):
    sup = get_supervisor()
    try:
        sup.stash_inspector.apply(index, drop=req.drop)
        await ws_manager.broadcast({"event": "stash_applied", "index": index})
        return {"success": True}
    except GitError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/stashes/{index}/drop")
async def drop_stash(index: int):
    sup = get_supervisor()
    try:
        sup.stash_inspector.drop(index)
        await ws_manager.broadcast({"event": "stash_dropped", "index": index})
        return {"success": True}
    except GitError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------------------------------------------------------
# WebSocket for Live Real-Time Dashboard Updates
# -----------------------------------------------------------------------------


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive & handle incoming pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# -----------------------------------------------------------------------------
# Static Dashboard Frontend
# -----------------------------------------------------------------------------

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(str(index_file))
    return {"message": "WorktreeForge Web Studio API running."}
