# arrowlane Docker benchmark

- Rows: 200000
- Repeats: 3
- Warmup repeats: 1
- Measured at: 2026-10-29T08:41:33+00:00
- Wire delta baseline: Python

| Implementation | Lane | Wire bytes | Wire delta | Encode ms | Decode ms |
|---|---:|---:|---:|---:|---:|
| python | json | 42505756 | +0 | 2572.575 | 1886.219 |
| python | ipc | 12670845 | +0 | 5.166 | 3.917 |
| python | ipc-zstd | 1680124 | +0 | 24.078 | 15.165 |
| rust | json | 42505812 | +56 | 212.330 | 1047.205 |
| rust | ipc | 12671117 | +272 | 1.393 | 2.409 |
| rust | ipc-zstd | 1625309 | -54815 | 25.095 | 10.273 |
| zig | json | 42372426 | -133330 | 172.880 | 311.182 |
| zig | ipc | 12670849 | +4 | 41.087 | 24.640 |
| zig | ipc-zstd | 1620045 | -60079 | 55.157 | 19.526 |
