# Quickstart for agents

## Install

```bash
pip install arrowlane
```

Add the server extra only when you serve frames over HTTP:

```bash
pip install "arrowlane[server]"
```

## Produce a frame

```python
import pyarrow as pa

import arrowlane

table = pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
wire, decision = arrowlane.transit(table, topology="same_network")
print(decision.lane, decision.reason, len(wire))
```

## Consume a frame

```python
table = arrowlane.unpack(wire)
assert table.num_rows == 3
```

## Serve a frame from ASGI

```python
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route

import arrowlane
from arrowlane.frame import FRAME_MEDIA_TYPE


async def table(request):
    data = arrowlane.to_table([{"id": 1}, {"id": 2}])
    wire, _ = arrowlane.transit(data, topology="same_network")
    return Response(wire, media_type=FRAME_MEDIA_TYPE)


app = Starlette(routes=[Route("/table", table)])
```

## Discover without reading source

```bash
arrowlane describe --indent 0
```

The same data is in `docs/ai/manifest.json`. Both come from the `describe()`
function in `arrowlane.describe`, and the test suite checks that they match.

## Large table

Use `pack_chunks` or `write_chunks`. One chunk is in flight, so a slow consumer
slows the producer. See `docs/ai/api.md` for the signatures and
`docs/ai/recipes.md` for a file stream.

## Next

- `docs/ai/api.md` for signatures and errors.
- `docs/ai/recipes.md` for service, file and in-process patterns.
