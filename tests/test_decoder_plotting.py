from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from canalyze.domain.dataset import FrameDataset
from canalyze.domain.models import CANFrame
from canalyze.services.dbc import DbcLoader
from canalyze.services.decoder import DecoderService
from canalyze.services.plotting import PlotModelBuilder
from canalyze.ui.view_helpers import materialize_filtered_rows


DBC_TEXT = """
BO_ 256 EngineData: 8 ECU
 SG_ Speed : 0|16@1+ (0.1,0) [0|250] "km/h" Vector__XXX
 SG_ Temp : 16|8@1+ (1,0) [-40|215] "C" Vector__XXX
""".strip()


class DecoderPlottingTests(unittest.TestCase):
    def test_decoder_loads_simple_dbc_and_builds_signal_samples(self) -> None:
        frames = [
            CANFrame(timestamp=0.0, can_id=0x100, dlc=8, data=bytes([0x64, 0x00, 0x1E, 0, 0, 0, 0, 0])),
            CANFrame(timestamp=0.5, can_id=0x999, dlc=1, data=bytes([0x01])),
        ]
        dataset = FrameDataset.from_frames(frames)

        with tempfile.TemporaryDirectory() as tmpdir:
            dbc_path = Path(tmpdir) / "sample.dbc"
            dbc_path.write_text(DBC_TEXT, encoding="utf-8")

            service = DecoderService()
            load_result = service.load_database(dbc_path)
            decoded = service.decode_dataset(dataset, load_result.database)

        self.assertEqual(decoded.decoded_messages[0].message_name, "EngineData")
        self.assertEqual(decoded.decoded_messages[0].decode_status, "decoded")
        self.assertEqual(decoded.decoded_messages[1].decode_status, "missing_definition")
        self.assertEqual(len(decoded.signal_samples), 2)
        self.assertEqual(decoded.signal_samples[0].name, "Speed")
        self.assertAlmostEqual(decoded.signal_samples[0].value, 10.0)

    def test_plot_builder_groups_signals_by_unit(self) -> None:
        frames = [
            CANFrame(timestamp=0.0, can_id=0x100, dlc=8, data=bytes([0x64, 0x00, 0x1E, 0, 0, 0, 0, 0])),
            CANFrame(timestamp=1.0, can_id=0x100, dlc=8, data=bytes([0xC8, 0x00, 0x28, 0, 0, 0, 0, 0])),
        ]
        dataset = FrameDataset.from_frames(frames)

        with tempfile.TemporaryDirectory() as tmpdir:
            dbc_path = Path(tmpdir) / "sample.dbc"
            dbc_path.write_text(DBC_TEXT, encoding="utf-8")

            service = DecoderService()
            load_result = service.load_database(dbc_path)
            decoded = service.decode_dataset(dataset, load_result.database)

        builder = PlotModelBuilder()
        groups = builder.build(
            decoded,
            selected_signals={("EngineData", "Speed"), ("EngineData", "Temp")},
        )

        self.assertEqual(len(groups), 2)
        units = [group.unit for group in groups]
        self.assertEqual(units, ["C", "km/h"])
        speed_group = next(group for group in groups if group.unit == "km/h")
        self.assertEqual(len(speed_group.series[0].x_values), 2)

    def test_dbc_loader_resolves_two_signal_conflict(self) -> None:
        overlapping = """
VERSION ""
NS_ :
BS_:
BU_: ECU
BO_ 517 TestMessage: 8 ECU
 SG_ KeepMe : 0|8@1+ (1,0) [0|255] "" ECU
 SG_ DropMe : 0|8@1+ (1,0) [0|255] "" ECU
""".strip()
        with tempfile.TemporaryDirectory() as tmpdir:
            dbc_path = Path(tmpdir) / "overlap.dbc"
            dbc_path.write_text(overlapping, encoding="utf-8")
            result = DbcLoader().load_file(
                dbc_path,
                pair_conflict_choices={
                    ("TestMessage", ("DropMe", "KeepMe")): "KeepMe",
                },
            )

        message = result.database.get_message_by_frame_id(517)
        self.assertEqual([signal.name for signal in message.signals], ["KeepMe"])
        self.assertEqual(len(result.warnings), 1)

    def test_dbc_loader_drops_multi_signal_conflict_group(self) -> None:
        overlapping = """
VERSION ""
NS_ :
BS_:
BU_: ECU
BO_ 517 TestMessage: 8 ECU
 SG_ A : 0|8@1+ (1,0) [0|255] "" ECU
 SG_ B : 0|8@1+ (1,0) [0|255] "" ECU
 SG_ C : 0|8@1+ (1,0) [0|255] "" ECU
 SG_ D : 8|8@1+ (1,0) [0|255] "" ECU
""".strip()
        with tempfile.TemporaryDirectory() as tmpdir:
            dbc_path = Path(tmpdir) / "overlap_many.dbc"
            dbc_path.write_text(overlapping, encoding="utf-8")
            result = DbcLoader().load_file(dbc_path)

        message = result.database.get_message_by_frame_id(517)
        self.assertEqual([signal.name for signal in message.signals], ["D"])
        self.assertEqual(len(result.warnings), 1)

    def test_refresh_views_materializes_table_rows_once(self) -> None:
        call_count = 0
        rows = [{"timestamp": float(index)} for index in range(6)]

        def counted_table_rows():
            nonlocal call_count
            call_count += 1
            return rows

        visible_rows = materialize_filtered_rows(counted_table_rows, [0, 2, 4])

        self.assertEqual(call_count, 1)
        self.assertEqual(visible_rows, [rows[0], rows[2], rows[4]])


if __name__ == "__main__":
    unittest.main()
