from __future__ import annotations

from collections import defaultdict

from canalyze.domain.dataset import FrameDataset
from canalyze.domain.models import PlotAxisGroup, PlotSeries


class PlotModelBuilder:
    def build(
        self,
        dataset: FrameDataset,
        selected_signals: set[tuple[str, str]],
        matched_indices: list[int] | None = None,
    ) -> list[PlotAxisGroup]:
        matched = set(matched_indices or range(len(dataset.frames)))
        grouped_series: dict[str, dict[str, PlotSeries]] = defaultdict(dict)

        for sample in dataset.signal_samples:
            key = (sample.message_name, sample.name)
            if key not in selected_signals or sample.frame_index not in matched:
                continue
            unit = sample.unit or "-"
            series_key = f"{sample.message_name}.{sample.name}"
            if series_key not in grouped_series[unit]:
                grouped_series[unit][series_key] = PlotSeries(
                    key=series_key,
                    message_name=sample.message_name,
                    signal_name=sample.name,
                    unit=sample.unit or "",
                    x_values=[],
                    y_values=[],
                    frame_indices=[],
                )
            series = grouped_series[unit][series_key]
            series.x_values.append(sample.timestamp)
            series.y_values.append(sample.value)
            series.frame_indices.append(sample.frame_index)

        axis_groups = [
            PlotAxisGroup(unit=unit, series=sorted(series.values(), key=lambda item: item.key))
            for unit, series in grouped_series.items()
        ]
        return sorted(axis_groups, key=lambda group: group.unit)
