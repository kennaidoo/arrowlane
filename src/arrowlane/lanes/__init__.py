"""Built-in lanes. Importing this module registers every built-in lane."""

from .base import Lane, LaneInfo, available_names, get_lane, lane_names, register
from .ipc_lane import IpcLane, decode_ipc, encode_ipc
from .json_lane import JsonLane
from .shm_lane import ShmLane
from .zstd_lane import ZstdLane

register(JsonLane())
register(IpcLane())
register(ZstdLane())
register(ShmLane())

__all__ = [
    "Lane",
    "LaneInfo",
    "available_names",
    "decode_ipc",
    "encode_ipc",
    "get_lane",
    "lane_names",
    "register",
]
