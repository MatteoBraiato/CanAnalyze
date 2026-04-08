from __future__ import annotations

from itertools import cycle

from canalyze.compat import HAS_PYQTGRAPH, HAS_PYSIDE6
from canalyze.domain.models import PlotAxisGroup

if HAS_PYSIDE6:
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
else:
    QWidget = object

if HAS_PYQTGRAPH and HAS_PYSIDE6:
    import pyqtgraph as pg
else:
    pg = None


class MultiAxisPlotWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._unit_views = []

        if pg is None:
            self._placeholder = QLabel(
                "pyqtgraph is not installed. Plotting is unavailable in this environment.",
                self,
            )
            self._placeholder.setWordWrap(True)
            self._layout.addWidget(self._placeholder)
            self._plot_widget = None
            return

        pg.setConfigOptions(antialias=False)
        self._plot_widget = pg.PlotWidget(parent=self)
        self._plot_widget.setBackground("w")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.25)
        self._plot_widget.addLegend(offset=(10, 10))
        self._layout.addWidget(self._plot_widget)

    def set_series(self, axis_groups: list[PlotAxisGroup]) -> None:
        if self._plot_widget is None:
            return

        plot_item = self._plot_widget.getPlotItem()
        self._clear_dynamic_axes(plot_item)
        plot_item.clear()
        if plot_item.legend is not None:
            plot_item.legend.clear()

        colors = cycle(["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b"])
        plot_item.setLabel("bottom", "Time", units="s")

        if not axis_groups:
            plot_item.setLabel("left", "Value")
            return

        base_view = plot_item.vb
        primary_group = axis_groups[0]
        plot_item.setLabel("left", primary_group.unit or "Value")
        for series in primary_group.series:
            plot_item.plot(
                series.x_values,
                series.y_values,
                pen=pg.mkPen(next(colors), width=2),
                name=f"{series.message_name}.{series.signal_name}",
                downsampleMethod="peak",
                clipToView=True,
                autoDownsample=True,
            )

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

            view_box = pg.ViewBox()
            plot_item.scene().addItem(view_box)
            axis.linkToView(view_box)
            view_box.setXLink(base_view)
            view_box.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
            view_box.setGeometry(base_view.sceneBoundingRect())

            for series in axis_group.series:
                label = f"{series.message_name}.{series.signal_name}"
                curve = pg.PlotCurveItem(
                    x=series.x_values,
                    y=series.y_values,
                    pen=pg.mkPen(next(colors), width=2),
                    autoDownsample=True,
                    clipToView=True,
                    downsampleMethod="peak",
                )
                view_box.addItem(curve)
                if plot_item.legend is not None:
                    plot_item.legend.addItem(curve, label)

            self._unit_views.append((view_box, axis, built_in_axis))

        self._sync_views()
        base_view.sigResized.connect(self._sync_views)
        base_view.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)
        base_view.autoRange()

    def _clear_dynamic_axes(self, plot_item) -> None:
        try:
            plot_item.vb.sigResized.disconnect(self._sync_views)
        except Exception:
            pass

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

    def _sync_views(self) -> None:
        if self._plot_widget is None:
            return
        scene_rect = self._plot_widget.getPlotItem().vb.sceneBoundingRect()
        for view_box, _axis, _built_in_axis in self._unit_views:
            view_box.setGeometry(scene_rect)
            view_box.linkedViewChanged(self._plot_widget.getPlotItem().vb, view_box.XAxis)
