"""ASGI service: one table, three portable lanes, one decision."""

from __future__ import annotations

import os

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from arrowlane.frame import FRAME_MEDIA_TYPE
from arrowlane.select import Topology
from arrowlane.transit import pack, plan, transit

from .data import table

MAX_ROWS = int(os.environ.get("ARROWLAND_MAX_ROWS", "1000000"))
LANES = ("json", "ipc", "ipc-zstd")


async def health(request: Request) -> JSONResponse:
    """Liveness probe."""
    return JSONResponse({"status": "ok"})


async def decision(request: Request) -> JSONResponse:
    """Explain the lane choice for the requested table."""
    rows = _rows(request)
    chosen = plan(table(rows), topology=Topology.SAME_NETWORK, allowed=LANES)
    return JSONResponse(chosen.as_dict())


async def table_bytes(request: Request) -> Response:
    """Serve the table as a frame on the requested or planned lane."""
    rows = _rows(request)
    data = table(rows)
    lane = request.query_params.get("lane")
    if lane is not None:
        if lane not in LANES:
            raise HTTPException(status_code=400, detail=f"lane must be one of {LANES}")
        wire = pack(data, lane=lane)
        used = lane
    else:
        wire, chosen = transit(data, topology=Topology.SAME_NETWORK, allowed=LANES)
        used = chosen.lane
    return Response(
        wire,
        media_type=FRAME_MEDIA_TYPE,
        headers={"x-arrowlane-lane": used, "x-arrowlane-rows": str(rows)},
    )


def _rows(request: Request) -> int:
    raw = request.query_params.get("rows", "1000")
    try:
        rows = int(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="rows must be an integer") from exc
    if not 0 <= rows <= MAX_ROWS:
        raise HTTPException(status_code=400, detail=f"rows must be between 0 and {MAX_ROWS}")
    return rows


app = Starlette(
    routes=[
        Route("/health", health),
        Route("/decision", decision),
        Route("/table", table_bytes),
    ]
)
