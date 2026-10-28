"""Property tests for the untrusted parsers."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from arrowlane.errors import ArrowLaneError
from arrowlane.frame import decode_frame
from arrowlane.shm import Descriptor


@given(st.binary(max_size=4096))
@settings(max_examples=500, deadline=None)
def test_decode_frame_never_raises_an_untyped_error(raw: bytes) -> None:
    try:
        decode_frame(raw)
    except ArrowLaneError:
        return


@given(st.binary(max_size=512))
@settings(max_examples=300, deadline=None)
def test_descriptor_never_raises_an_untyped_error(raw: bytes) -> None:
    try:
        Descriptor.from_bytes(raw)
    except ArrowLaneError:
        return
