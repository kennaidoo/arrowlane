# Integration recipes

## 1. In-process pipeline

```python
import pyarrow as pa

import arrowlane

source = pa.table({"id": list(range(1000))})
wire, decision = arrowlane.transit(source, topology="same_host")
restored = arrowlane.unpack(wire)
assert restored.equals(source)
print(decision.lane)
```

## 2. ASGI producer and client

Producer:

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

Client:

```python
import urllib.request

import arrowlane

with urllib.request.urlopen("http://127.0.0.1:8000/table", timeout=30) as response:
    table = arrowlane.unpack(response.read())
print(table.num_rows)
```

## 3. A frame on disk

```python
import pathlib

import pyarrow as pa

import arrowlane

table = pa.table({"id": [1, 2, 3]})
wire, _ = arrowlane.transit(table, topology="same_host")
pathlib.Path("frame.aln").write_bytes(wire)
restored = arrowlane.unpack(pathlib.Path("frame.aln").read_bytes())
assert restored.equals(table)
```

The frame is self-describing, so the reader needs no side channel.

## 4. Choose a lane without sending

```python
import pyarrow as pa

import arrowlane

table = pa.table({"id": list(range(100_000))})
decision = arrowlane.plan(table, topology="wide_area")
print(decision.as_dict())
```

## 5. Discover the capability manifest from a build

```python
import json
import subprocess

manifest = json.loads(
    subprocess.check_output(["arrowlane", "describe", "--indent", "0"], text=True)
)
print(manifest["package_version"], [lane["name"] for lane in manifest["lanes"]])
```

The static copy is `docs/ai/manifest.json`, and the tests require it to equal
`arrowlane.describe.describe()`.

## Failure handling

```python
import arrowlane
from arrowlane.errors import ArrowLaneError

try:
    table = arrowlane.unpack(wire)
except ArrowLaneError as exc:
    print(f"frame rejected: {exc}")
```

Catch `ArrowLaneError`, not bare `Exception`. Every library error derives from it.
