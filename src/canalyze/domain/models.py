from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CANFrame:
    timestamp: float
    can_id: int
    dlc: int
    data: bytes
    channel: str | None = None
    direction: str | None = None
    frame_type: str = "data"
    source_line: int | None = None


@dataclass(slots=True)
class SignalSample:
    name: str
    value: float
    unit: str
    timestamp: float
    message_name: str
    can_id: int
    frame_index: int


@dataclass(slots=True)
class DecodedSignal:
    name: str
    value: Any
    unit: str = ""


@dataclass(slots=True)
class DecodedMessage:
    frame_index: int
    can_id: int
    message_name: str | None
    signals: list[DecodedSignal] = field(default_factory=list)
    decode_status: str = "not_decoded"
    warning: str | None = None


@dataclass(slots=True)
class FilterCriteria:
    can_ids: set[int] | None = None
    time_start: float | None = None
    time_end: float | None = None
    message_names: set[str] | None = None


@dataclass(slots=True)
class WarningEntry:
    source: str
    message: str
    line_number: int | None = None


@dataclass(slots=True)
class SignalDescriptor:
    message_name: str
    signal_name: str
    unit: str


@dataclass(slots=True)
class PlotSeries:
    key: str
    message_name: str
    signal_name: str
    unit: str
    x_values: list[float]
    y_values: list[float]
    frame_indices: list[int]


@dataclass(slots=True)
class PlotAxisGroup:
    unit: str
    series: list[PlotSeries] = field(default_factory=list)
