from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from canalyze.compat import HAS_CANTOOLS
from canalyze.domain.models import WarningEntry

if HAS_CANTOOLS:
    import cantools
    from cantools.database.utils import start_bit as cantools_start_bit
else:
    cantools = None
    cantools_start_bit = None


@dataclass(slots=True)
class SimpleSignalDefinition:
    name: str
    start_bit: int
    length: int
    byte_order: str
    signed: bool
    factor: float
    offset: float
    unit: str


@dataclass(slots=True)
class SimpleMessageDefinition:
    frame_id: int
    name: str
    dlc: int
    signals: list[SimpleSignalDefinition] = field(default_factory=list)


class SimpleDbcDatabase:
    def __init__(self, messages: dict[int, SimpleMessageDefinition]) -> None:
        self.messages = messages

    def get_message_by_frame_id(self, frame_id: int) -> SimpleMessageDefinition:
        if frame_id not in self.messages:
            raise KeyError(frame_id)
        return self.messages[frame_id]

    def decode_message(self, frame_id: int, data: bytes) -> dict[str, float]:
        message = self.get_message_by_frame_id(frame_id)
        return {
            signal.name: _decode_signal_value(signal, data)
            for signal in message.signals
        }


@dataclass(slots=True)
class DbcConflict:
    message_name: str
    signal_names: tuple[str, ...]


@dataclass(slots=True)
class DbcLoadResult:
    database: Any
    warnings: list[WarningEntry] = field(default_factory=list)


class DbcLoader:
    def __init__(self) -> None:
        self.using_cantools = HAS_CANTOOLS

    def load_file(
        self,
        path: str | Path,
        pair_conflict_choices: dict[tuple[str, tuple[str, ...]], str | None] | None = None,
    ) -> DbcLoadResult:
        if cantools is not None:
            return self._load_cantools_database(path, pair_conflict_choices)
        return DbcLoadResult(database=_load_simple_dbc(path))

    def inspect_conflicts(self, path: str | Path) -> list[DbcConflict]:
        if cantools is None:
            return []
        text = Path(path).read_text(encoding="cp1252", errors="replace")
        database = cantools.database.load_string(text, database_format="dbc", strict=False)
        return _find_overlapping_signal_groups(database)

    def _load_cantools_database(
        self,
        path: str | Path,
        pair_conflict_choices: dict[tuple[str, tuple[str, ...]], str | None] | None = None,
    ) -> DbcLoadResult:
        try:
            database = cantools.database.load_file(str(path))
            return DbcLoadResult(database=database)
        except Exception:
            text = Path(path).read_text(encoding="cp1252", errors="replace")
            database = cantools.database.load_string(text, database_format="dbc", strict=False)
            conflicts = _find_overlapping_signal_groups(database)
            if not conflicts:
                raise

            pair_conflict_choices = pair_conflict_choices or {}

            drop_map: dict[str, set[str]] = {}
            warnings: list[WarningEntry] = []
            for conflict in conflicts:
                signals = set(conflict.signal_names)
                if len(conflict.signal_names) == 2:
                    selected = pair_conflict_choices.get(_conflict_key(conflict))
                    if selected in signals:
                        signals.remove(selected)
                        dropped_signal = sorted(signals)[0]
                        warnings.append(
                            WarningEntry(
                                "dbc",
                                f"Kept signal {selected} and ignored conflicting signal "
                                f"{dropped_signal} in message {conflict.message_name}.",
                            )
                        )
                    else:
                        warnings.append(
                            WarningEntry(
                                "dbc",
                                f"Ignored conflicting signals {', '.join(conflict.signal_names)} "
                                f"in message {conflict.message_name}.",
                            )
                        )
                else:
                    warnings.append(
                        WarningEntry(
                            "dbc",
                            f"Ignored conflicting signals {', '.join(conflict.signal_names)} "
                            f"in message {conflict.message_name}.",
                        )
                    )
                drop_map.setdefault(conflict.message_name, set()).update(signals)

            sanitized_text = _remove_signals_from_dbc_text(text, drop_map)
            database = cantools.database.load_string(sanitized_text, database_format="dbc", strict=True)
            return DbcLoadResult(database=database, warnings=warnings)


BO_RE = re.compile(r"^BO_\s+(?P<frame_id>\d+)\s+(?P<name>\w+)\s*:\s*(?P<dlc>\d+)")
DBC_SG_NAME_RE = re.compile(r"^\s*SG_\s+(?P<name>[^ :]+)")
SG_RE = re.compile(
    r"^SG_\s+(?P<name>\w+)\s*:\s*"
    r"(?P<start>\d+)\|(?P<length>\d+)@(?P<byte_order>[01])(?P<signed>[+-])\s*"
    r"\((?P<factor>[-0-9.]+),(?P<offset>[-0-9.]+)\)\s*"
    r"\[(?P<min>[-0-9.]+)\|(?P<max>[-0-9.]+)\]\s*"
    r"\"(?P<unit>[^\"]*)\""
)


def _load_simple_dbc(path: str | Path) -> SimpleDbcDatabase:
    messages: dict[int, SimpleMessageDefinition] = {}
    current_message: SimpleMessageDefinition | None = None
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        bo_match = BO_RE.match(stripped)
        if bo_match:
            current_message = SimpleMessageDefinition(
                frame_id=int(bo_match.group("frame_id")),
                name=bo_match.group("name"),
                dlc=int(bo_match.group("dlc")),
            )
            messages[current_message.frame_id] = current_message
            continue
        if current_message is None:
            continue
        sg_match = SG_RE.match(stripped)
        if sg_match:
            current_message.signals.append(
                SimpleSignalDefinition(
                    name=sg_match.group("name"),
                    start_bit=int(sg_match.group("start")),
                    length=int(sg_match.group("length")),
                    byte_order="little_endian"
                    if sg_match.group("byte_order") == "1"
                    else "big_endian",
                    signed=sg_match.group("signed") == "-",
                    factor=float(sg_match.group("factor")),
                    offset=float(sg_match.group("offset")),
                    unit=sg_match.group("unit"),
                )
            )
    return SimpleDbcDatabase(messages)


def _decode_signal_value(signal: SimpleSignalDefinition, data: bytes) -> float:
    if signal.byte_order != "little_endian":
        raise NotImplementedError("Fallback DBC decoder only supports little-endian signals.")
    raw = int.from_bytes(data.ljust(8, b"\x00"), byteorder="little", signed=False)
    mask = (1 << signal.length) - 1
    value = (raw >> signal.start_bit) & mask
    if signal.signed and signal.length > 0:
        sign_bit = 1 << (signal.length - 1)
        if value & sign_bit:
            value -= 1 << signal.length
    return (value * signal.factor) + signal.offset


def _find_overlapping_signal_groups(database: Any) -> list[DbcConflict]:
    conflicts: list[DbcConflict] = []
    for message in getattr(database, "messages", []):
        groups = _find_message_conflict_groups(message)
        for signal_names in groups:
            conflicts.append(
                DbcConflict(
                    message_name=getattr(message, "name", f"0x{getattr(message, 'frame_id', 0):X}"),
                    signal_names=tuple(sorted(signal_names)),
                )
            )
    return conflicts


def _find_message_conflict_groups(message: Any) -> list[set[str]]:
    graph: dict[str, set[str]] = {}
    message_bits = [None] * (8 * getattr(message, "length", 0))
    for signal in getattr(message, "signals", []):
        graph.setdefault(signal.name, set())
        signal_bits = _signal_bits_for_overlap_check(signal, len(message_bits))
        for offset, signal_bit in enumerate(signal_bits):
            if signal_bit is None:
                continue
            if message_bits[offset] is not None:
                other = message_bits[offset]
                graph.setdefault(other, set()).add(signal.name)
                graph[signal.name].add(other)
            else:
                message_bits[offset] = signal.name

    groups: list[set[str]] = []
    seen: set[str] = set()
    for signal_name, overlaps in graph.items():
        if not overlaps or signal_name in seen:
            continue
        component = set()
        stack = [signal_name]
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(graph.get(current, set()) - component)
        seen.update(component)
        if len(component) > 1:
            groups.append(component)
    return groups


def _signal_bits_for_overlap_check(signal: Any, message_bit_length: int) -> list[str | None]:
    signal_bits: list[str | None] = [signal.name] * signal.length
    if signal.byte_order == "big_endian":
        padding = cantools_start_bit(signal) * [None]
        signal_bits = padding + signal_bits
    else:
        signal_bits += signal.start * [None]
        if len(signal_bits) < message_bit_length:
            padding = (message_bit_length - len(signal_bits)) * [None]
            reversed_signal_bits = padding + signal_bits
        else:
            reversed_signal_bits = signal_bits

        signal_bits = []
        for index in range(0, len(reversed_signal_bits), 8):
            signal_bits = reversed_signal_bits[index : index + 8] + signal_bits

    return signal_bits


def _remove_signals_from_dbc_text(text: str, drop_map: dict[str, set[str]]) -> str:
    if not drop_map:
        return text

    kept_lines: list[str] = []
    current_message_name: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        bo_match = BO_RE.match(stripped)
        if bo_match:
            current_message_name = bo_match.group("name")
            kept_lines.append(line)
            continue

        sg_match = DBC_SG_NAME_RE.match(line)
        if current_message_name and sg_match:
            signal_name = sg_match.group("name")
            if signal_name in drop_map.get(current_message_name, set()):
                continue

        kept_lines.append(line)

    return "\n".join(kept_lines) + ("\n" if text.endswith("\n") else "")


def _conflict_key(conflict: DbcConflict) -> tuple[str, tuple[str, ...]]:
    return (conflict.message_name, conflict.signal_names)
