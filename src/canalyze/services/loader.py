from __future__ import annotations

from pathlib import Path

from canalyze.domain.dataset import FrameDataset
from canalyze.domain.models import WarningEntry
from canalyze.services.parsers import ParserRegistry, UnsupportedLogFormatError


class DatasetLoader:
    def __init__(self, parser_registry: ParserRegistry | None = None) -> None:
        self.parser_registry = parser_registry or ParserRegistry()

    def load(self, log_path: str | Path) -> FrameDataset:
        parser = self.parser_registry.parser_for(log_path)
        parse_result = parser.parse(log_path)
        dataset = FrameDataset.from_frames(parse_result.frames, parse_result.warnings)
        if not dataset.frames:
            dataset.warnings.append(
                WarningEntry("loader", "No CAN frames were loaded from the selected file.")
            )
        return dataset

    def supported_file_types(self) -> tuple[str, ...]:
        return self.parser_registry.supported_extensions()

    @staticmethod
    def describe_unsupported_extension(log_path: str | Path) -> str:
        suffix = Path(log_path).suffix.lower() or "<none>"
        return (
            f"Unsupported log format '{suffix}'. "
            "v1 currently supports .asc and .trc files."
        )
