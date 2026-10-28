# arrowlane

Columnar data lanes for ingress and egress in containerized Python apps.

Status: Alpha. The API may change. Python 3.14 or newer.

Test coverage is enforced on Linux, where the POSIX shared memory lanes run.

## Quick start

```python
import pyarrow as pa

import arrowlane

table = pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
wire, decision = arrowlane.transit(table, topology="same_network")
rows = arrowlane.unpack(wire).num_rows
print(decision.lane, len(wire), rows)
```
