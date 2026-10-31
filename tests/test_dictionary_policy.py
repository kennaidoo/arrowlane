"""The dictionary subset the format defines, enforced at the lane boundary.

The C++ port accepts only int32 indices, unordered, with utf8 or binary values.
A frame outside that subset is rejected there, so this package has to reject it
too or the two disagree about what a valid frame is.
"""

from __future__ import annotations

import pyarrow as pa
import pytest

from arrowlane.errors import FrameError
from arrowlane.frame import Frame, header_for
from arrowlane.lanes.ipc_lane import IpcLane, encode_ipc


def _dictionary_table(
    index_type: pa.DataType | None = None,
    ordered: bool = False,
    values: pa.Array | None = None,
) -> pa.Table:
    index_type = pa.int32() if index_type is None else index_type
    dictionary = pa.array(["ozow", "payfast"] if values is None else values)
    indices = pa.array([0, 1, 0], type=index_type)
    kind = pa.dictionary(index_type, dictionary.type, ordered=ordered)
    column = pa.DictionaryArray.from_arrays(indices, dictionary).cast(kind)
    return pa.table({"merchant": column})


def test_plain_dictionary_round_trips() -> None:
    lane = IpcLane()
    table = _dictionary_table()
    out = lane.decode(lane.encode(table))
    assert out.equals(table)


def test_binary_dictionary_round_trips() -> None:
    lane = IpcLane()
    table = _dictionary_table(values=pa.array([b"a", b"b"]))
    out = lane.decode(lane.encode(table))
    assert out.equals(table)


def test_ordered_dictionary_is_rejected_on_encode() -> None:
    with pytest.raises(FrameError, match="ordered"):
        IpcLane().encode(_dictionary_table(ordered=True))


def test_wide_index_is_rejected_on_encode() -> None:
    with pytest.raises(FrameError, match="int32"):
        IpcLane().encode(_dictionary_table(index_type=pa.int64()))


def test_ordered_dictionary_is_rejected_on_decode() -> None:
    # Build the frame without the lane, so the policy is the only thing that can
    # reject it.
    table = _dictionary_table(ordered=True)
    raw = encode_ipc(table)
    header = header_for(table, media_type="application/vnd.apache.arrow.stream")
    frame = Frame(2, raw, table.num_rows, len(raw), header)
    with pytest.raises(FrameError, match="ordered"):
        IpcLane().decode(frame)
