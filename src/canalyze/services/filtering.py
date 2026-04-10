from __future__ import annotations

from canalyze.domain.dataset import FrameDataset
from canalyze.domain.models import CanMessageIdentity, FilterCriteria


class FilterEngine:
    def apply(self, dataset: FrameDataset, criteria: FilterCriteria) -> list[int]:
        matched_indices: list[int] = []
        decoded_by_index = {
            decoded.frame_index: decoded for decoded in dataset.decoded_messages
        }
        for index, frame in enumerate(dataset.frames):
            if criteria.can_message_pairs:
                decoded = decoded_by_index.get(index)
                identity = CanMessageIdentity(
                    can_id=frame.can_id,
                    message_name=decoded.message_name if decoded and decoded.message_name else None,
                )
                if identity not in criteria.can_message_pairs:
                    continue
            if criteria.can_ids and frame.can_id not in criteria.can_ids:
                continue
            if criteria.time_start is not None and frame.timestamp < criteria.time_start:
                continue
            if criteria.time_end is not None and frame.timestamp > criteria.time_end:
                continue
            if criteria.message_names:
                decoded = decoded_by_index.get(index)
                if decoded is None or not decoded.message_name or decoded.message_name not in criteria.message_names:
                    continue
            matched_indices.append(index)
        return matched_indices

    def filtered_signal_keys(
        self,
        dataset: FrameDataset,
        matched_indices: list[int],
    ) -> set[tuple[str, str]]:
        matched = set(matched_indices)
        return {
            (sample.message_name, sample.name)
            for sample in dataset.signal_samples
            if sample.frame_index in matched
        }
