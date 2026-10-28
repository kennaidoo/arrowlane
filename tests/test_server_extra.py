"""The server extra must serve bytes on the patched Starlette line."""

from __future__ import annotations

import pytest


def test_server_extra_serves_bytes() -> None:
    pytest.importorskip("starlette")
    from starlette.applications import Starlette
    from starlette.responses import Response
    from starlette.routing import Route
    from starlette.testclient import TestClient

    async def table(request: object) -> Response:
        return Response(b"ALN1", media_type="application/vnd.arrowlane.frame")

    app = Starlette(routes=[Route("/table", table)])
    with TestClient(app) as client:
        response = client.get("/table")
    assert response.status_code == 200
    assert response.content == b"ALN1"
    assert response.headers["content-type"] == "application/vnd.arrowlane.frame"
