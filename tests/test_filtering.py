from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from canalyze.domain.dataset import FrameDataset
from canalyze.domain.models import (
    CANFrame,
    CanMessageIdentity,
    DecodedMessage,
    DecodedSignal,
    FilterCriteria,
    SignalSample,
)
from canalyze.services.filtering import FilterEngine


class FilterEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        frames = [
            CANFrame(timestamp=0.0, can_id=0x100, dlc=1, data=b"\x01"),
            CANFrame(timestamp=0.5, can_id=0x200, dlc=1, data=b"\x02"),
            CANFrame(timestamp=1.0, can_id=0x100, dlc=1, data=b"\x03"),
        ]
        self.dataset = FrameDataset.from_frames(frames)
        self.dataset.attach_decode_results(
            [
                DecodedMessage(0, 0x100, "EngineData", [DecodedSignal("Speed", 1.0, "km/h")], "decoded"),
                DecodedMessage(1, 0x200, "BrakeData", [DecodedSignal("Pressure", 2.0, "bar")], "decoded"),
                DecodedMessage(2, 0x100, "EngineData", [DecodedSignal("Speed", 3.0, "km/h")], "decoded"),
            ],
            [
                SignalSample("Speed", 1.0, "km/h", 0.0, "EngineData", 0x100, 0),
                SignalSample("Pressure", 2.0, "bar", 0.5, "BrakeData", 0x200, 1),
                SignalSample("Speed", 3.0, "km/h", 1.0, "EngineData", 0x100, 2),
            ],
        )
        self.engine = FilterEngine()

    def test_filter_by_can_id_and_time_range(self) -> None:
        indices = self.engine.apply(
            self.dataset,
            FilterCriteria(can_ids={0x100}, time_start=0.2, time_end=1.0),
        )
        self.assertEqual(indices, [2])

    def test_filter_by_message_name_and_signal_key_projection(self) -> None:
        indices = self.engine.apply(
            self.dataset,
            FilterCriteria(message_names={"EngineData"}),
        )
        self.assertEqual(indices, [0, 2])
        signal_keys = self.engine.filtered_signal_keys(self.dataset, indices)
        self.assertEqual(signal_keys, {(0x100, "EngineData", "Speed")})

    def test_filter_by_combined_can_message_pair_is_pair_exact(self) -> None:
        dataset = FrameDataset.from_frames(
            [
                CANFrame(timestamp=0.0, can_id=0x100, dlc=1, data=b"\x01"),
                CANFrame(timestamp=0.5, can_id=0x100, dlc=1, data=b"\x02"),
                CANFrame(timestamp=1.0, can_id=0x200, dlc=1, data=b"\x03"),
            ]
        )
        dataset.attach_decode_results(
            [
                DecodedMessage(0, 0x100, "EngineData", [], "decoded"),
                DecodedMessage(1, 0x100, "BrakeData", [], "decoded"),
                DecodedMessage(2, 0x200, "BrakeData", [], "decoded"),
            ],
            [],
        )

        indices = self.engine.apply(
            dataset,
            FilterCriteria(
                can_message_pairs={CanMessageIdentity(0x100, "BrakeData")},
            ),
        )

        self.assertEqual(indices, [1])


if __name__ == "__main__":
    unittest.main()
