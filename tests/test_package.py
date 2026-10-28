"""Package level checks."""

import arrowlane


def test_version_is_pinned() -> None:
    assert arrowlane.__version__ == "0.1.0"


def test_public_api() -> None:
    assert set(arrowlane.__all__) == {
        "__version__",
        "Frame",
        "decode_frame",
        "encode_frame",
        "to_table",
    }
