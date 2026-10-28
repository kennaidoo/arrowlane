"""Package level checks."""

import arrowlane


def test_version_is_set() -> None:
    assert arrowlane.__version__.count(".") == 2


def test_public_api() -> None:
    assert set(arrowlane.__all__) == {
        "ArrowLaneError",
        "ChunkError",
        "ChunkInfo",
        "Decision",
        "Frame",
        "Policy",
        "Topology",
        "Workload",
        "__version__",
        "assemble_chunks",
        "decode_frame",
        "encode_frame",
        "pack",
        "pack_chunks",
        "plan",
        "read_chunks",
        "read_frame",
        "to_table",
        "transit",
        "transit_chunks",
        "unpack",
        "unpack_chunks",
        "write_chunks",
        "write_frame",
    }
