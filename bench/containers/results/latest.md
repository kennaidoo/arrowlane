# arrowlane Docker benchmark

- Rows: 200000
- Repeats: 3
- Warmup repeats: 1
- Measured at: 2026-10-29T09:31:16+00:00
- Wire delta baseline: Python

| Implementation | Lane | Wire bytes | Wire delta | Encode ms | Decode ms |
|---|---:|---:|---:|---:|---:|
| python | json | 42505756 | +0 | 2167.805 | 2074.545 |
| python | ipc | 12670845 | +0 | 18.522 | 3.354 |
| python | ipc-zstd | 1680124 | +0 | 24.300 | 21.325 |
| rust | json | 42505812 | +56 | 261.699 | 1228.560 |
| rust | ipc | 12671117 | +272 | 1.457 | 2.598 |
| rust | ipc-zstd | 1625309 | -54815 | 24.684 | 10.031 |
| zig | json | 42372426 | -133330 | 182.791 | 351.653 |
| zig | ipc | 12670849 | +4 | 45.149 | 27.161 |
| zig | ipc-zstd | 1620045 | -60079 | 61.658 | 21.626 |
