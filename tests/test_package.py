"""Package level checks."""

import arrowlane


def test_version_is_set() -> None:
    assert arrowlane.__version__.count(".") == 2


def test_public_api() -> None:
    assert set(arrowlane.__all__) == {
        "Decision",
        "Frame",
        "Policy",
        "Topology",
        "Workload",
        "__version__",
        "decode_frame",
        "encode_frame",
        "pack",
        "plan",
        "to_table",
        "transit",
        "unpack",
    }
