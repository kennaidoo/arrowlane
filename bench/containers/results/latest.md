# arrowlane Docker benchmark

- Rows: 200000
- Repeats: 3
- Warmup repeats: 1
- Measured at: 2026-10-29T08:04:13+00:00
- Wire delta baseline: Python

| Implementation | Lane | Wire bytes | Wire delta | Encode ms | Decode ms |
|---|---:|---:|---:|---:|---:|
| python | json | 42505756 | +0 | 3111.630 | 2624.323 |
| python | ipc | 12670845 | +0 | 5.283 | 3.331 |
| python | ipc-zstd | 1680124 | +0 | 23.082 | 15.948 |
| rust | json | 42505812 | +56 | 228.862 | 1034.057 |
| rust | ipc | 12671117 | +272 | 1.812 | 2.613 |
| rust | ipc-zstd | 1625309 | -54815 | 24.052 | 10.075 |
| zig | json | 42372426 | -133330 | 173.382 | 323.423 |
| zig | ipc | 12670849 | +4 | 43.122 | 24.621 |
| zig | ipc-zstd | 1620045 | -60079 | 55.257 | 179.177 |
