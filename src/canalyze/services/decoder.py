from __future__ import annotations

from pathlib import Path
from typing import Any

from canalyze.compat import HAS_CANTOOLS
from canalyze.domain.dataset import FrameDataset
from canalyze.domain.models import DecodedMessage, DecodedSignal, SignalSample, WarningEntry
from canalyze.services.dbc import DbcLoadResult, DbcLoader, SimpleDbcDatabase


class DecoderService:
    def __init__(self, dbc_loader: DbcLoader | None = None) -> None:
        self.dbc_loader = dbc_loader or DbcLoader()

    def inspect_database_conflicts(self, dbc_path: str | Path):
        return self.dbc_loader.inspect_conflicts(dbc_path)

    def load_database(self, dbc_path: str | Path, pair_conflict_choices=None) -> DbcLoadResult:
        return self.dbc_loader.load_file(dbc_path, pair_conflict_choices)

    def decode_dataset(self, dataset: FrameDataset, database: Any) -> FrameDataset:
        decoded_messages: list[DecodedMessage] = []
        signal_samples: list[SignalSample] = []
        warnings: list[WarningEntry] = []

        for index, frame in enumerate(dataset.frames):
            decoded = self.decode_frame(index, frame.can_id, frame.data, database)
            decoded_messages.append(decoded)
            if decoded.warning:
                warnings.append(WarningEntry("decoder", decoded.warning, frame.source_line))
            for signal in decoded.signals:
                if isinstance(signal.value, bool):
                    numeric_value = 1.0 if signal.value else 0.0
                else:
                    try:
                        numeric_value = float(signal.value)
                    except (TypeError, ValueError):
                        continue
                signal_samples.append(
                    SignalSample(
                        name=signal.name,
                        value=numeric_value,
                        unit=signal.unit or "",
                        timestamp=frame.timestamp,
                        message_name=decoded.message_name or f"0x{frame.can_id:X}",
                        can_id=frame.can_id,
                        frame_index=index,
                    )
                )

        dataset.attach_decode_results(decoded_messages, signal_samples)
        dataset.warnings.extend(warnings)
        return dataset

    def decode_frame(
        self,
        frame_index: int,
        can_id: int,
        data: bytes,
        database: Any,
    ) -> DecodedMessage:
        message = self._get_message(database, can_id)
        if message is None:
            return DecodedMessage(
                frame_index=frame_index,
                can_id=can_id,
                message_name=None,
                signals=[],
                decode_status="missing_definition",
                warning=f"No DBC message definition found for CAN ID 0x{can_id:X}.",
            )

        try:
            values = database.decode_message(can_id, data)
        except Exception as exc:
            return DecodedMessage(
                frame_index=frame_index,
                can_id=can_id,
                message_name=self._message_name(message),
                signals=[],
                decode_status="decode_error",
                warning=f"Failed to decode CAN ID 0x{can_id:X}: {exc}",
            )

        signals: list[DecodedSignal] = []
        for signal_name, value in values.items():
            signals.append(
                DecodedSignal(
                    name=signal_name,
                    value=value,
                    unit=self._signal_unit(message, signal_name),
                )
            )
        return DecodedMessage(
            frame_index=frame_index,
            can_id=can_id,
            message_name=self._message_name(message),
            signals=signals,
            decode_status="decoded",
            warning=None,
        )

    def _get_message(self, database: Any, can_id: int) -> Any | None:
        try:
            return database.get_message_by_frame_id(can_id)
        except Exception:
            return None

    @staticmethod
    def _message_name(message: Any) -> str:
        return getattr(message, "name", "")

    def _signal_unit(self, message: Any, signal_name: str) -> str:
        signals = getattr(message, "signals", [])
        for signal in signals:
            if getattr(signal, "name", None) == signal_name:
                return getattr(signal, "unit", "") or ""
        return ""
