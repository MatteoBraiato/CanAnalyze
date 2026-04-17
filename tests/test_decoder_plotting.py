from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from canalyze.compat import HAS_PYQTGRAPH, HAS_PYSIDE6
from canalyze.domain.dataset import FrameDataset
from canalyze.domain.models import CANFrame, PlotAxisGroup, PlotSeries
from canalyze.services.dbc import DbcLoader
from canalyze.services.decoder import DecoderService
from canalyze.services.plotting import PlotModelBuilder
from canalyze.ui.plot_widget import CLEAR_PLOT_COLORS, MultiAxisPlotWidget
from canalyze.ui.view_helpers import materialize_filtered_rows

if HAS_PYSIDE6:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtWidgets import QApplication
else:
    QApplication = None


DBC_TEXT = """
BO_ 256 EngineData: 8 ECU
 SG_ Speed : 0|16@1+ (0.1,0) [0|250] "km/h" Vector__XXX
 SG_ Temp : 16|8@1+ (1,0) [-40|215] "C" Vector__XXX
""".strip()


class DecoderPlottingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if HAS_PYSIDE6:
            cls._app = QApplication.instance() or QApplication([])
        else:
            cls._app = None

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
            selected_signals={(0x100, "EngineData", "Speed"), (0x100, "EngineData", "Temp")},
        )

        self.assertEqual(len(groups), 2)
        units = [group.unit for group in groups]
        self.assertEqual(units, ["C", "km/h"])
        speed_group = next(group for group in groups if group.unit == "km/h")
        self.assertEqual(len(speed_group.series[0].x_values), 2)
        self.assertEqual(speed_group.series[0].frame_indices, [0, 1])

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

    def test_plot_widget_renders_single_series(self) -> None:
        if not (HAS_PYSIDE6 and HAS_PYQTGRAPH):
            self.skipTest("Qt plotting dependencies are not installed")

        widget = MultiAxisPlotWidget()
        self.addCleanup(widget.deleteLater)

        widget.set_series(
            [
                PlotAxisGroup(
                    unit="%",
                    series=[
                        PlotSeries(
                            key="Message.Signal",
                            can_id=0x100,
                            message_name="Message",
                            signal_name="Signal",
                            unit="%",
                            x_values=[0.0, 1.0, 2.0],
                            y_values=[1.0, 2.0, 3.0],
                            frame_indices=[10, 11, 12],
                        )
                    ],
                )
            ]
        )

        plot_item = widget._plot_widget.getPlotItem()
        self.assertEqual(len(plot_item.listDataItems()), 1)
        self.assertIsNotNone(plot_item.legend)
        self.assertEqual(len(plot_item.legend.items), 1)

        widget.set_series(
            [
                PlotAxisGroup(
                    unit="%",
                    series=[
                        PlotSeries(
                            key="Message.Signal2",
                            can_id=0x100,
                            message_name="Message",
                            signal_name="Signal2",
                            unit="%",
                            x_values=[0.0, 1.0],
                            y_values=[4.0, 5.0],
                            frame_indices=[20, 21],
                        )
                    ],
                )
            ]
        )

        plot_item = widget._plot_widget.getPlotItem()
        self.assertEqual(len(plot_item.listDataItems()), 1)
        self.assertEqual(len(plot_item.legend.items), 1)

    def test_plot_widget_keeps_existing_signal_color_when_adding_series(self) -> None:
        if not (HAS_PYSIDE6 and HAS_PYQTGRAPH):
            self.skipTest("Qt plotting dependencies are not installed")

        widget = MultiAxisPlotWidget()
        self.addCleanup(widget.deleteLater)

        first_series = PlotSeries(
            key="Message.SignalA",
            can_id=0x100,
            message_name="Message",
            signal_name="SignalA",
            unit="%",
            x_values=[0.0, 1.0],
            y_values=[1.0, 2.0],
            frame_indices=[1, 2],
        )
        second_series = PlotSeries(
            key="Message.SignalB",
            can_id=0x200,
            message_name="Message",
            signal_name="SignalB",
            unit="%",
            x_values=[0.0, 1.0],
            y_values=[4.0, 5.0],
            frame_indices=[3, 4],
        )

        widget.set_series([PlotAxisGroup(unit="%", series=[first_series])])
        first_color = widget._series_colors["Message.SignalA"]

        widget.set_series([PlotAxisGroup(unit="%", series=[first_series, second_series])])

        self.assertEqual(widget._series_colors["Message.SignalA"], first_color)
        self.assertIn(widget._series_colors["Message.SignalB"], CLEAR_PLOT_COLORS)
        self.assertNotEqual(widget._series_colors["Message.SignalA"], widget._series_colors["Message.SignalB"])

    def test_plot_widget_manual_color_change_persists_across_redraws(self) -> None:
        if not (HAS_PYSIDE6 and HAS_PYQTGRAPH):
            self.skipTest("Qt plotting dependencies are not installed")

        widget = MultiAxisPlotWidget()
        self.addCleanup(widget.deleteLater)

        series = PlotSeries(
            key="Message.Signal",
            can_id=0x100,
            message_name="Message",
            signal_name="Signal",
            unit="%",
            x_values=[0.0, 1.0],
            y_values=[1.0, 2.0],
            frame_indices=[10, 11],
        )
        widget.set_series([PlotAxisGroup(unit="%", series=[series])])

        widget._set_series_color(series.key, "#16A085")
        widget.set_series([PlotAxisGroup(unit="%", series=[series])])

        self.assertEqual(widget._series_colors[series.key], "#16A085")
        self.assertEqual(
            widget._curve_records[0].curve.opts["pen"].color().name().upper(),
            "#16A085",
        )

    def test_plot_widget_renders_secondary_axis_groups(self) -> None:
        if not (HAS_PYSIDE6 and HAS_PYQTGRAPH):
            self.skipTest("Qt plotting dependencies are not installed")

        widget = MultiAxisPlotWidget()
        self.addCleanup(widget.deleteLater)

        widget.set_series(
            [
                PlotAxisGroup(
                    unit="%",
                    series=[
                        PlotSeries(
                            key="Message.SignalA",
                            can_id=0x100,
                            message_name="Message",
                            signal_name="SignalA",
                            unit="%",
                            x_values=[0.0, 1.0],
                            y_values=[1.0, 2.0],
                            frame_indices=[30, 31],
                        )
                    ],
                ),
                PlotAxisGroup(
                    unit="Hz",
                    series=[
                        PlotSeries(
                            key="Message.SignalB",
                            can_id=0x200,
                            message_name="Message",
                            signal_name="SignalB",
                            unit="Hz",
                            x_values=[0.0, 1.0],
                            y_values=[10.0, 20.0],
                            frame_indices=[40, 41],
                        )
                    ],
                ),
            ]
        )

        plot_item = widget._plot_widget.getPlotItem()
        self.assertEqual(len(plot_item.listDataItems()), 1)
        self.assertEqual(len(widget._unit_views), 1)
        self.assertTrue(plot_item.getAxis("right").isVisible())
        self.assertEqual(len(plot_item.legend.items), 2)

    def test_plot_widget_finds_hovered_sample_on_secondary_axis(self) -> None:
        if not (HAS_PYSIDE6 and HAS_PYQTGRAPH):
            self.skipTest("Qt plotting dependencies are not installed")

        widget = MultiAxisPlotWidget()
        self.addCleanup(widget.deleteLater)
        widget.resize(640, 480)
        widget.show()
        self._app.processEvents()

        widget.set_series(
            [
                PlotAxisGroup(
                    unit="%",
                    series=[
                        PlotSeries(
                            key="Message.SignalA",
                            can_id=0x100,
                            message_name="Message",
                            signal_name="SignalA",
                            unit="%",
                            x_values=[0.0, 1.0],
                            y_values=[1.0, 2.0],
                            frame_indices=[30, 31],
                        )
                    ],
                ),
                PlotAxisGroup(
                    unit="Hz",
                    series=[
                        PlotSeries(
                            key="Message.SignalB",
                            can_id=0x200,
                            message_name="Message",
                            signal_name="SignalB",
                            unit="Hz",
                            x_values=[0.0, 1.0],
                            y_values=[10.0, 20.0],
                            frame_indices=[40, 41],
                        )
                    ],
                ),
            ]
        )
        self._app.processEvents()

        secondary_view = widget._unit_views[0][0]
        scene_point = secondary_view.mapViewToScene(QPointF(1.0, 20.0))

        hovered = widget._find_closest_sample(scene_point)

        self.assertIsNotNone(hovered)
        assert hovered is not None
        self.assertEqual(hovered.record.series.signal_name, "SignalB")
        self.assertEqual(hovered.sample_index, 1)

    def test_plot_widget_click_emits_hovered_frame_index(self) -> None:
        if not (HAS_PYSIDE6 and HAS_PYQTGRAPH):
            self.skipTest("Qt plotting dependencies are not installed")

        widget = MultiAxisPlotWidget()
        self.addCleanup(widget.deleteLater)

        widget.set_series(
            [
                PlotAxisGroup(
                    unit="%",
                    series=[
                        PlotSeries(
                            key="Message.Signal",
                            can_id=0x100,
                            message_name="Message",
                            signal_name="Signal",
                            unit="%",
                            x_values=[0.0, 1.0],
                            y_values=[1.0, 2.0],
                            frame_indices=[50, 51],
                        )
                    ],
                )
            ]
        )

        emitted: list[int] = []
        widget.sampleActivated.connect(emitted.append)
        widget._hovered_sample = widget._find_closest_sample(
            widget._plot_widget.getPlotItem().vb.mapViewToScene(QPointF(1.0, 2.0))
        )

        class FakeClickEvent:
            @staticmethod
            def button():
                return Qt.MouseButton.LeftButton

        widget._on_scene_mouse_clicked(FakeClickEvent())

        self.assertEqual(emitted, [51])

    def test_plot_widget_enables_context_menu_for_primary_and_secondary_axes(self) -> None:
        if not (HAS_PYSIDE6 and HAS_PYQTGRAPH):
            self.skipTest("Qt plotting dependencies are not installed")

        widget = MultiAxisPlotWidget()
        self.addCleanup(widget.deleteLater)

        widget.set_series(
            [
                PlotAxisGroup(
                    unit="%",
                    series=[
                        PlotSeries(
                            key="Message.SignalA",
                            can_id=0x100,
                            message_name="Message",
                            signal_name="SignalA",
                            unit="%",
                            x_values=[0.0, 1.0],
                            y_values=[1.0, 2.0],
                            frame_indices=[30, 31],
                        )
                    ],
                ),
                PlotAxisGroup(
                    unit="Hz",
                    series=[
                        PlotSeries(
                            key="Message.SignalB",
                            can_id=0x200,
                            message_name="Message",
                            signal_name="SignalB",
                            unit="Hz",
                            x_values=[0.0, 1.0],
                            y_values=[10.0, 20.0],
                            frame_indices=[40, 41],
                        )
                    ],
                ),
            ]
        )

        base_view = widget._plot_widget.getPlotItem().vb
        self.assertTrue(base_view.menuEnabled())
        self.assertEqual(len(widget._unit_views), 1)
        self.assertTrue(widget._unit_views[0][0].menuEnabled())

    def test_view_box_right_click_raises_context_menu(self) -> None:
        if not (HAS_PYSIDE6 and HAS_PYQTGRAPH):
            self.skipTest("Qt plotting dependencies are not installed")

        widget = MultiAxisPlotWidget()
        self.addCleanup(widget.deleteLater)

        widget.set_series(
            [
                PlotAxisGroup(
                    unit="%",
                    series=[
                        PlotSeries(
                            key="Message.Signal",
                            can_id=0x100,
                            message_name="Message",
                            signal_name="Signal",
                            unit="%",
                            x_values=[0.0, 1.0],
                            y_values=[1.0, 2.0],
                            frame_indices=[10, 11],
                        )
                    ],
                )
            ]
        )

        base_view = widget._plot_widget.getPlotItem().vb
        raised_events = []

        def record_raise_context_menu(event) -> None:
            raised_events.append(event)

        base_view.raiseContextMenu = record_raise_context_menu

        class FakeRightClickEvent:
            def __init__(self) -> None:
                self.accepted = False

            @staticmethod
            def button():
                return Qt.MouseButton.RightButton

            def accept(self) -> None:
                self.accepted = True

        event = FakeRightClickEvent()
        base_view.mouseClickEvent(event)

        self.assertTrue(event.accepted)
        self.assertEqual(raised_events, [event])


if __name__ == "__main__":
    unittest.main()
