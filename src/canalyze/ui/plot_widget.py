from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
import math

from canalyze.compat import HAS_PYSIDE6
from canalyze.domain.models import PlotAxisGroup, PlotSeries

if HAS_PYSIDE6:
    from PySide6.QtCore import QPoint, QPointF, Qt, Signal
    from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
    from PySide6.QtWidgets import QLabel, QMenu, QVBoxLayout, QWidget
else:
    QWidget = object
    Signal = lambda *_args, **_kwargs: None

_PYQTGRAPH_IMPORT_ERROR: Exception | None = None

if HAS_PYSIDE6:
    try:
        import pyqtgraph as pg
    except Exception as exc:
        pg = None
        _PYQTGRAPH_IMPORT_ERROR = exc
else:
    pg = None
    _PYQTGRAPH_IMPORT_ERROR = ImportError("PySide6 is not installed.")


CLEAR_PLOT_COLORS = [
    "#2E86DE",
    "#E74C3C",
    "#27AE60",
    "#F39C12",
    "#8E44AD",
    "#16A085",
    "#C0392B",
    "#2980B9",
    "#D35400",
    "#7F8C8D",
    "#1ABC9C",
    "#B9770E",
]


@dataclass(slots=True)
class _CurveRecord:
    curve: object
    view_box: object
    series: PlotSeries


@dataclass(slots=True)
class _HoveredSample:
    record: _CurveRecord
    sample_index: int
    distance_pixels: float
    scene_point: QPointF


def get_plotting_unavailable_reason() -> str | None:
    if _PYQTGRAPH_IMPORT_ERROR is None:
        return None

    return str(_PYQTGRAPH_IMPORT_ERROR) or _PYQTGRAPH_IMPORT_ERROR.__class__.__name__


class MultiAxisPlotWidget(QWidget):
    sampleActivated = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._unit_views = []
        self._curve_records: list[_CurveRecord] = []
        self._hovered_sample: _HoveredSample | None = None
        self._legend_targets: dict[object, str] = {}
        self._series_colors: dict[str, str] = {}
        self._palette_index = 0
        self._view_sync_connected = False
        self._background_color = "w"
        self._grid_alpha = 0.25
        self._axis_color = "#1c1f24"
        self._hover_background = "#ffffff"
        self._hover_border = "#c9ced6"
        self._hover_text = "#1c1f24"

        if pg is None:
            message = "pyqtgraph plotting is unavailable in this environment."
            reason = get_plotting_unavailable_reason()
            if reason:
                message = f"{message}\n\nReason: {reason}"
            self._placeholder = QLabel(message, self)
            self._placeholder.setWordWrap(True)
            self._layout.addWidget(self._placeholder)
            self._plot_widget = None
            self._hover_label = None
            return

        pg.setConfigOptions(antialias=False)
        self._plot_widget = pg.PlotWidget(parent=self)
        self._plot_widget.setBackground(self._background_color)
        self._plot_widget.showGrid(x=True, y=True, alpha=self._grid_alpha)
        self._plot_widget.addLegend(offset=(10, 10))
        self._layout.addWidget(self._plot_widget)

        self._hover_label = QLabel(self)
        self._hover_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._hover_label.hide()

        scene = self._plot_widget.scene()
        self._mouse_proxy = pg.SignalProxy(scene.sigMouseMoved, rateLimit=60, slot=self._on_scene_mouse_moved)
        scene.sigMouseClicked.connect(self._on_scene_mouse_clicked)
        self._apply_theme_to_plot()

    def set_theme(self, theme_name: str) -> None:
        if theme_name == "dark":
            self._background_color = "#11151b"
            self._grid_alpha = 0.18
            self._axis_color = "#eef2f7"
            self._hover_background = "#20242c"
            self._hover_border = "#475264"
            self._hover_text = "#eef2f7"
        else:
            self._background_color = "w"
            self._grid_alpha = 0.25
            self._axis_color = "#1c1f24"
            self._hover_background = "#ffffff"
            self._hover_border = "#c9ced6"
            self._hover_text = "#1c1f24"
        self._apply_theme_to_plot()

    def set_series(self, axis_groups: list[PlotAxisGroup]) -> None:
        if self._plot_widget is None:
            return

        plot_item = self._plot_widget.getPlotItem()
        self._clear_dynamic_axes(plot_item)
        plot_item.clear()
        self._clear_legend(plot_item)
        self._curve_records.clear()
        self._clear_hover_state()
        self._apply_theme_to_plot()
        plot_item.setLabel("bottom", "Time", units="s")

        if not axis_groups:
            plot_item.setLabel("left", "Value")
            return

        base_view = plot_item.vb
        base_view.setMouseEnabled(x=True, y=True)
        base_view.setMenuEnabled(True)
        primary_group = axis_groups[0]
        plot_item.setLabel("left", primary_group.unit or "Value")
        for series in primary_group.series:
            series_color = self._ensure_series_color(series.key)
            curve = plot_item.plot(
                series.x_values,
                series.y_values,
                pen=pg.mkPen(series_color, width=2),
                name=f"0x{series.can_id:X} | {series.message_name}.{series.signal_name}",
                downsampleMethod="peak",
                autoDownsample=True,
            )
            self._curve_records.append(_CurveRecord(curve=curve, view_box=base_view, series=series))
            self._register_legend_item(plot_item, series.key)

        if len(axis_groups) == 1:
            base_view.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)
            base_view.autoRange()
            return

        for offset, axis_group in enumerate(axis_groups[1:], start=1):
            built_in_axis = offset == 1
            if built_in_axis:
                axis = plot_item.getAxis("right")
                plot_item.showAxis("right", True)
            else:
                axis = pg.AxisItem("right")
                plot_item.layout.addItem(axis, 2, 3 + offset - 1)
            axis.setLabel(axis_group.unit or "Value")

            view_box = pg.ViewBox(enableMenu=True)
            plot_item.scene().addItem(view_box)
            axis.linkToView(view_box)
            view_box.setXLink(base_view)
            view_box.setMouseEnabled(x=False, y=False)
            view_box.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
            view_box.setGeometry(base_view.sceneBoundingRect())

            for series in axis_group.series:
                label = f"0x{series.can_id:X} | {series.message_name}.{series.signal_name}"
                series_color = self._ensure_series_color(series.key)
                curve = pg.PlotCurveItem(
                    x=series.x_values,
                    y=series.y_values,
                    pen=pg.mkPen(series_color, width=2),
                    autoDownsample=True,
                    downsampleMethod="peak",
                )
                view_box.addItem(curve)
                self._curve_records.append(_CurveRecord(curve=curve, view_box=view_box, series=series))
                if plot_item.legend is not None:
                    plot_item.legend.addItem(curve, label)
                    self._register_legend_item(plot_item, series.key)

            self._unit_views.append((view_box, axis, built_in_axis))

        self._sync_views()
        if not self._view_sync_connected:
            base_view.sigResized.connect(self._sync_views)
            base_view.sigRangeChanged.connect(self._sync_views)
            self._view_sync_connected = True
        base_view.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)
        base_view.autoRange()

    def _clear_legend(self, plot_item) -> None:
        self._legend_targets.clear()
        if plot_item.legend is None:
            return
        entries = [label.text for _sample, label in plot_item.legend.items]
        for entry in entries:
            plot_item.legend.removeItem(entry)

    def _apply_theme_to_plot(self) -> None:
        if self._plot_widget is None:
            return
        self._plot_widget.setBackground(self._background_color)
        plot_item = self._plot_widget.getPlotItem()
        plot_item.showGrid(x=True, y=True, alpha=self._grid_alpha)
        for axis_name in ("left", "bottom", "right"):
            axis = plot_item.getAxis(axis_name)
            axis.setPen(self._axis_color)
            axis.setTextPen(self._axis_color)
        if self._hover_label is not None:
            self._hover_label.setStyleSheet(
                "\n".join(
                    [
                        f"background-color: {self._hover_background};",
                        f"border: 1px solid {self._hover_border};",
                        f"color: {self._hover_text};",
                        "border-radius: 6px;",
                        "padding: 6px 8px;",
                    ]
                )
            )

    def _clear_dynamic_axes(self, plot_item) -> None:
        if self._view_sync_connected:
            try:
                plot_item.vb.sigResized.disconnect(self._sync_views)
            except Exception:
                pass
            try:
                plot_item.vb.sigRangeChanged.disconnect(self._sync_views)
            except Exception:
                pass
            self._view_sync_connected = False

        plot_item.showAxis("right", False)
        plot_item.getAxis("right").setLabel("")

        for view_box, axis, built_in_axis in self._unit_views:
            scene = plot_item.scene()
            scene.removeItem(view_box)
            if built_in_axis:
                continue
            plot_item.layout.removeItem(axis)
            scene.removeItem(axis)
        self._unit_views.clear()

    def _sync_views(self, *_args) -> None:
        if self._plot_widget is None:
            return
        plot_item = self._plot_widget.getPlotItem()
        scene_rect = plot_item.vb.sceneBoundingRect()
        for view_box, _axis, _built_in_axis in self._unit_views:
            view_box.setGeometry(scene_rect)
            view_box.linkedViewChanged(plot_item.vb, view_box.XAxis)

    def _on_scene_mouse_moved(self, event) -> None:
        if self._plot_widget is None:
            return

        scene_position = event[0]
        hovered_sample = self._find_closest_sample(scene_position)
        if hovered_sample is None:
            self._clear_hover_state()
            return

        self._hovered_sample = hovered_sample
        self._show_hover_label(hovered_sample)

    def _on_scene_mouse_clicked(self, event) -> None:
        if self._handle_legend_click(event):
            return
        if event.button() != Qt.MouseButton.LeftButton or self._hovered_sample is None:
            return
        frame_index = self._hovered_sample.record.series.frame_indices[self._hovered_sample.sample_index]
        self.sampleActivated.emit(frame_index)

    def _handle_legend_click(self, event) -> bool:
        if self._plot_widget is None or event.button() != Qt.MouseButton.LeftButton:
            return False
        scene_position = event.scenePos() if hasattr(event, "scenePos") else None
        if scene_position is None:
            return False

        series_key = self._legend_target_for_scene_pos(scene_position)
        if series_key is None:
            return False

        self._show_color_menu(series_key, event)
        return True

    def _legend_target_for_scene_pos(self, scene_position: QPointF) -> str | None:
        if self._plot_widget is None:
            return None
        for item in self._plot_widget.scene().items(scene_position):
            current = item
            while current is not None:
                if current in self._legend_targets:
                    return self._legend_targets[current]
                current = current.parentItem() if hasattr(current, "parentItem") else None
        return None

    def _show_color_menu(self, series_key: str, event) -> None:
        menu = QMenu(self)
        current_color = self._series_colors.get(series_key)
        for color in CLEAR_PLOT_COLORS:
            label = f"{color} {'(Current)' if color == current_color else ''}".strip()
            action = menu.addAction(self._color_icon(color), label)
            action.triggered.connect(
                lambda _checked=False, key=series_key, selected_color=color: self._set_series_color(
                    key, selected_color
                )
            )

        if hasattr(event, "screenPos"):
            screen_position = event.screenPos()
            if isinstance(screen_position, QPointF):
                menu.exec(QPoint(int(screen_position.x()), int(screen_position.y())))
                return
            if isinstance(screen_position, QPoint):
                menu.exec(screen_position)
                return

        if hasattr(event, "scenePos") and self._plot_widget is not None:
            widget_pos = self._plot_widget.mapFromScene(event.scenePos())
            menu.exec(self._plot_widget.mapToGlobal(widget_pos))

    def _register_legend_item(self, plot_item, series_key: str) -> None:
        if plot_item.legend is None or not plot_item.legend.items:
            return
        sample, label = plot_item.legend.items[-1]
        self._legend_targets[sample] = series_key
        self._legend_targets[label] = series_key

    def _ensure_series_color(self, series_key: str) -> str:
        existing_color = self._series_colors.get(series_key)
        if existing_color is not None:
            return existing_color

        assigned_colors = set(self._series_colors.values())
        for _index in range(len(CLEAR_PLOT_COLORS)):
            palette_color = CLEAR_PLOT_COLORS[self._palette_index % len(CLEAR_PLOT_COLORS)]
            self._palette_index += 1
            if palette_color not in assigned_colors:
                self._series_colors[series_key] = palette_color
                return palette_color

        palette_color = CLEAR_PLOT_COLORS[self._palette_index % len(CLEAR_PLOT_COLORS)]
        self._palette_index += 1
        self._series_colors[series_key] = palette_color
        return palette_color

    def _set_series_color(self, series_key: str, color: str) -> None:
        self._series_colors[series_key] = color
        if pg is None:
            return

        for record in self._curve_records:
            if record.series.key != series_key:
                continue
            record.curve.setPen(pg.mkPen(color, width=2))
            if hasattr(record.curve, "update"):
                record.curve.update()

    @staticmethod
    def _color_icon(color: str) -> QIcon:
        pixmap = QPixmap(18, 18)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QColor("#d0d6df"))
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(1, 1, 16, 16, 4, 4)
        painter.end()
        return QIcon(pixmap)

    def _find_closest_sample(self, scene_position: QPointF) -> _HoveredSample | None:
        if self._plot_widget is None or not self._curve_records:
            return None

        threshold_pixels = 14.0
        best_match: _HoveredSample | None = None

        for record in self._curve_records:
            series = record.series
            if not series.x_values:
                continue

            view_box = record.view_box
            if not view_box.sceneBoundingRect().contains(scene_position):
                continue

            hovered = self._candidate_hover_for_record(record, scene_position, threshold_pixels)
            if hovered is None:
                continue
            if best_match is None or hovered.distance_pixels < best_match.distance_pixels:
                best_match = hovered

        return best_match

    def _candidate_hover_for_record(
        self,
        record: _CurveRecord,
        scene_position: QPointF,
        threshold_pixels: float,
    ) -> _HoveredSample | None:
        series = record.series
        view_position = record.view_box.mapSceneToView(scene_position)
        insertion_index = bisect_left(series.x_values, view_position.x())
        candidate_indices = sorted(
            index
            for index in {
                insertion_index - 2,
                insertion_index - 1,
                insertion_index,
                insertion_index + 1,
                insertion_index + 2,
            }
            if 0 <= index < len(series.x_values)
        )
        if not candidate_indices:
            return None

        scene_points = {
            index: record.view_box.mapViewToScene(
                QPointF(series.x_values[index], series.y_values[index])
            )
            for index in candidate_indices
        }

        best_match: _HoveredSample | None = None
        for index, point in scene_points.items():
            distance = self._distance(scene_position, point)
            if distance > threshold_pixels:
                continue
            hovered = _HoveredSample(
                record=record,
                sample_index=index,
                distance_pixels=distance,
                scene_point=point,
            )
            if best_match is None or hovered.distance_pixels < best_match.distance_pixels:
                best_match = hovered

        for left_index, right_index in (
            (insertion_index - 1, insertion_index),
            (insertion_index, insertion_index + 1),
        ):
            if not (0 <= left_index < len(series.x_values) and 0 <= right_index < len(series.x_values)):
                continue
            left_point = scene_points.get(left_index) or record.view_box.mapViewToScene(
                QPointF(series.x_values[left_index], series.y_values[left_index])
            )
            right_point = scene_points.get(right_index) or record.view_box.mapViewToScene(
                QPointF(series.x_values[right_index], series.y_values[right_index])
            )
            segment_distance = self._distance_to_segment(scene_position, left_point, right_point)
            if segment_distance > threshold_pixels:
                continue

            nearest_index = (
                left_index
                if abs(view_position.x() - series.x_values[left_index])
                <= abs(view_position.x() - series.x_values[right_index])
                else right_index
            )
            nearest_point = left_point if nearest_index == left_index else right_point
            hovered = _HoveredSample(
                record=record,
                sample_index=nearest_index,
                distance_pixels=segment_distance,
                scene_point=nearest_point,
            )
            if best_match is None or hovered.distance_pixels < best_match.distance_pixels:
                best_match = hovered

        return best_match

    def _show_hover_label(self, hovered_sample: _HoveredSample) -> None:
        if self._hover_label is None or self._plot_widget is None:
            return

        series = hovered_sample.record.series
        sample_index = hovered_sample.sample_index
        unit_suffix = f" {series.unit}" if series.unit else ""
        self._hover_label.setText(
            "\n".join(
                [
                    f"0x{series.can_id:X} | {series.message_name}.{series.signal_name}",
                    f"t: {series.x_values[sample_index]:.6f} s",
                    f"y: {series.y_values[sample_index]:g}{unit_suffix}",
                ]
            )
        )
        self._hover_label.adjustSize()

        widget_position = self._plot_widget.mapFromScene(hovered_sample.scene_point)
        label_x = min(
            max(widget_position.x() + 14, 0),
            max(self.width() - self._hover_label.width() - 4, 0),
        )
        label_y = min(
            max(widget_position.y() - self._hover_label.height() - 14, 0),
            max(self.height() - self._hover_label.height() - 4, 0),
        )
        self._hover_label.move(label_x, label_y)
        self._hover_label.show()

    def _clear_hover_state(self) -> None:
        self._hovered_sample = None
        if self._hover_label is not None:
            self._hover_label.hide()

    @staticmethod
    def _distance(first: QPointF, second: QPointF) -> float:
        return math.hypot(first.x() - second.x(), first.y() - second.y())

    @classmethod
    def _distance_to_segment(cls, point: QPointF, start: QPointF, end: QPointF) -> float:
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        segment_length_sq = dx * dx + dy * dy
        if segment_length_sq == 0:
            return cls._distance(point, start)

        projection = (
            ((point.x() - start.x()) * dx) + ((point.y() - start.y()) * dy)
        ) / segment_length_sq
        projection = max(0.0, min(1.0, projection))
        closest_point = QPointF(start.x() + projection * dx, start.y() + projection * dy)
        return cls._distance(point, closest_point)
