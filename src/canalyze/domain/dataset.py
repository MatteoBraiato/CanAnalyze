from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from canalyze.compat import HAS_NUMPY, HAS_PANDAS
from canalyze.domain.models import CANFrame, DecodedMessage, SignalSample, WarningEntry

if HAS_NUMPY:
    import numpy as np
else:
    np = None

if HAS_PANDAS:
    import pandas as pd
else:
    pd = None


@dataclass(slots=True)
class FrameDataset:
    frames: list[CANFrame]
    warnings: list[WarningEntry] = field(default_factory=list)
    decoded_messages: list[DecodedMessage] = field(default_factory=list)
    signal_samples: list[SignalSample] = field(default_factory=list)
    frame_table: Any = None
    raw_matrix: Any = None

    @classmethod
    def from_frames(
        cls,
        frames: list[CANFrame],
        warnings: list[WarningEntry] | None = None,
    ) -> "FrameDataset":
        dataset = cls(frames=frames, warnings=warnings or [])
        dataset.frame_table = _build_frame_table(frames)
        dataset.raw_matrix = _build_raw_matrix(frames)
        return dataset

    def attach_decode_results(
        self,
        decoded_messages: list[DecodedMessage],
        signal_samples: list[SignalSample],
    ) -> None:
        self.decoded_messages = decoded_messages
        self.signal_samples = signal_samples
        self.frame_table = _augment_frame_table(self.frame_table, decoded_messages)


def _build_frame_table(frames: list[CANFrame]) -> Any:
    rows = [
        {
            "timestamp": frame.timestamp,
            "can_id": frame.can_id,
            "can_id_hex": f"0x{frame.can_id:X}",
            "dlc": frame.dlc,
            "data_hex": frame.data.hex(" ").upper(),
            "channel": frame.channel or "",
            "direction": frame.direction or "",
            "frame_type": frame.frame_type,
            "message_name": "",
            "decode_status": "not_decoded",
            "warning": "",
        }
        for frame in frames
    ]
    if pd is not None:
        return pd.DataFrame(rows)
    return rows


def _augment_frame_table(frame_table: Any, decoded_messages: list[DecodedMessage]) -> Any:
    if pd is not None and frame_table is not None:
        frame_table = frame_table.copy()
        frame_table["message_name"] = [
            message.message_name or "" for message in decoded_messages
        ]
        frame_table["decode_status"] = [message.decode_status for message in decoded_messages]
        frame_table["warning"] = [message.warning or "" for message in decoded_messages]
        return frame_table

    table = list(frame_table or [])
    for row, message in zip(table, decoded_messages):
        row["message_name"] = message.message_name or ""
        row["decode_status"] = message.decode_status
        row["warning"] = message.warning or ""
    return table


def _build_raw_matrix(frames: list[CANFrame]) -> Any:
    rows = []
    for frame in frames:
        row = []
        for index in range(8):
            if index < len(frame.data):
                value = frame.data[index]
                row.append({"hex": f"{value:02X}", "int": value})
            else:
                row.append({"hex": "--", "int": None})
        rows.append(row)

    if np is not None:
        return np.array(rows, dtype=object)
    return rows
