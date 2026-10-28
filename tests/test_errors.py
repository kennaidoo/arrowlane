"""Error hierarchy contract."""

import pytest

from arrowlane import errors


@pytest.mark.parametrize(
    "name",
    [
        "ConfigError",
        "FrameError",
        "BadMagic",
        "UnsupportedVersion",
        "TruncatedFrame",
        "OversizeFrame",
        "ChecksumMismatch",
        "UnknownLane",
        "BadHeader",
        "LaneUnavailable",
        "SegmentError",
        "SegmentGone",
        "AuthError",
        "LimitExceeded",
        "UpstreamError",
    ],
)
def test_error_exists_and_is_catchable(name: str) -> None:
    cls = getattr(errors, name)
    assert issubclass(cls, errors.ArrowLaneError)
    with pytest.raises(errors.ArrowLaneError):
        raise cls("boom")


def test_frame_errors_are_grouped() -> None:
    assert issubclass(errors.BadMagic, errors.FrameError)
    assert issubclass(errors.TruncatedFrame, errors.FrameError)
    assert issubclass(errors.ChecksumMismatch, errors.FrameError)
