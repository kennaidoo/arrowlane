"""Read what the C++ implementation wrote, when it is available.

The two repositories test their own bytes. This is the one place they meet: the
C++ test writes a dictionary stream, and this package has to accept it. The path
comes from an environment variable so neither repository depends on the other's
layout.
"""

from __future__ import annotations

import os
from pathlib import Path

import pyarrow as pa
import pytest

from arrowlane.frame import read_frame
from arrowlane.lanes.ipc_lane import check_dictionary_policy, decode_ipc, IpcLane


def _cpp_frame() -> Path:
    configured = os.environ.get("ARROWLANE_CPP_FRAME")
    if not configured:
        pytest.skip("set ARROWLANE_CPP_FRAME to a frame written by pack --dictionary")
    path = Path(configured)
    if not path.exists():
        pytest.skip(f"{path} does not exist")
    return path


def test_decodes_a_dictionary_frame_from_the_cpp_cli() -> None:
    with _cpp_frame().open("rb") as stream:
        frame = read_frame(stream)
    assert frame is not None
    table = IpcLane().decode(frame)
    field = table.schema.field("merchant")
    assert pa.types.is_dictionary(field.type)
    assert not field.type.ordered
    assert field.type.index_type == pa.int32()
    assert table.column("merchant").to_pylist() == ["ozow", "payfast", "ozow"]


def _cpp_stream() -> Path:
    configured = os.environ.get("ARROWLANE_CPP_DICT")
    if not configured:
        pytest.skip("set ARROWLANE_CPP_DICT to arrowlane-cpp's build/dict_cpp.arrows")
    path = Path(configured)
    if not path.exists():
        pytest.skip(f"{path} does not exist")
    return path


def test_reads_a_dictionary_stream_from_the_cpp_writer() -> None:
    table = decode_ipc(_cpp_stream().read_bytes())
    check_dictionary_policy(table.schema)
    field = table.schema.field("merchant")
    assert pa.types.is_dictionary(field.type)
    assert field.type.index_type == pa.int32()
    assert not field.type.ordered
    assert table.column("merchant").to_pylist() == ["ozow", "payfast", "ozow"]
