"""Exception hierarchy. Everything raised by arrowlane is an ArrowLaneError."""


class ArrowLaneError(Exception):
    """Root of every arrowlane error."""


class ConfigError(ArrowLaneError):
    """Configuration is missing or invalid."""


class FrameError(ArrowLaneError):
    """The frame cannot be trusted or decoded."""


class BadMagic(FrameError):
    """The frame does not start with the arrowlane magic."""


class UnsupportedVersion(FrameError):
    """The frame format version is not supported."""


class TruncatedFrame(FrameError):
    """The frame is shorter than its own length fields claim."""


class OversizeFrame(FrameError):
    """A length field exceeds a configured limit."""


class ChecksumMismatch(FrameError):
    """The payload does not match the frame CRC."""


class UnknownLane(FrameError):
    """The lane id is not registered."""


class BadHeader(FrameError):
    """The frame header is not valid JSON or carries no schema."""


class LaneUnavailable(ArrowLaneError):
    """The lane exists but this platform or directory cannot serve it."""


class SegmentError(ArrowLaneError):
    """A shared memory segment is missing, malformed or the wrong size."""


class SegmentGone(SegmentError):
    """The segment was already consumed."""


class AuthError(ArrowLaneError):
    """The caller is not authorised."""


class LimitExceeded(ArrowLaneError):
    """A runtime limit was hit, for example concurrency or body size."""


class UpstreamError(ArrowLaneError):
    """The upstream application failed."""
