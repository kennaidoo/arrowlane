# arrowlane Docker benchmark

- Rows: 200000
- Repeats: 5
- Warmup repeats: 1
- Measured at: 2026-10-29T11:53:24+00:00
- Wire delta baseline: Python

| Implementation | Lane | Wire bytes | Wire delta | Encode ms | Decode ms |
|---|---:|---:|---:|---:|---:|
| python | json | 42505756 | +0 | 2128.138 | 2062.808 |
| python | ipc | 12670845 | +0 | 20.367 | 3.593 |
| python | ipc-zstd | 1620041 | +0 | 28.866 | 19.947 |
| rust | json | 42505812 | +56 | 285.456 | 1240.968 |
| rust | ipc | 12671117 | +272 | 1.867 | 3.010 |
| rust | ipc-zstd | 1625309 | +5268 | 28.816 | 11.124 |
| zig | json | 42372426 | -133330 | 181.983 | 328.907 |
| zig | ipc | 12670849 | +4 | 44.976 | 25.996 |
| zig | ipc-zstd | 1620045 | +4 | 60.151 | 21.330 |
