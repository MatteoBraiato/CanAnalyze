from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path

from canalyze.domain.models import CANFrame, WarningEntry


HEX_ID_RE = re.compile(r"^[0-9A-Fa-f]+x?$")
BYTE_RE = re.compile(r"^[0-9A-Fa-f]{2}$")


class ParseResult:
    def __init__(self, frames: list[CANFrame], warnings: list[WarningEntry]) -> None:
        self.frames = frames
        self.warnings = warnings


class LogParser(ABC):
    extensions: tuple[str, ...] = ()

    @abstractmethod
    def parse(self, path: str | Path) -> ParseResult:
        raise NotImplementedError


class UnsupportedLogFormatError(ValueError):
    pass


class BaseTextLogParser(LogParser):
    def parse(self, path: str | Path) -> ParseResult:
        frames: list[CANFrame] = []
        warnings: list[WarningEntry] = []
        base_timestamp: float | None = None
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            parsed = self.parse_line(line, line_number)
            if parsed is None:
                continue
            if isinstance(parsed, WarningEntry):
                warnings.append(parsed)
                continue
            if base_timestamp is None:
                base_timestamp = parsed.timestamp
            frames.append(
                CANFrame(
                    timestamp=parsed.timestamp - (base_timestamp or 0.0),
                    can_id=parsed.can_id,
                    dlc=parsed.dlc,
                    data=parsed.data,
                    channel=parsed.channel,
                    direction=parsed.direction,
                    frame_type=parsed.frame_type,
                    source_line=parsed.source_line,
                )
            )
        return ParseResult(frames=frames, warnings=warnings)

    @abstractmethod
    def parse_line(self, line: str, line_number: int) -> CANFrame | WarningEntry | None:
        raise NotImplementedError


class AscParser(BaseTextLogParser):
    extensions = (".asc",)
    _skip_prefixes = ("//", "date ", "base ", "Begin Triggerblock", "End TriggerBlock")

    def parse_line(self, line: str, line_number: int) -> CANFrame | WarningEntry | None:
        stripped = line.strip()
        if not stripped or stripped.startswith(self._skip_prefixes):
            return None

        tokens = stripped.split()
        if len(tokens) < 5:
            return WarningEntry("asc", f"Skipped malformed ASC line: {stripped}", line_number)

        timestamp = _parse_float_token(tokens[0])
        if timestamp is None:
            return WarningEntry("asc", f"Skipped malformed timestamp: {stripped}", line_number)

        index = 1
        channel = None
        if index < len(tokens) and tokens[index].isdigit():
            channel = tokens[index]
            index += 1

        can_id = None
        while index < len(tokens):
            maybe_id = _parse_can_id(tokens[index])
            if maybe_id is not None:
                can_id = maybe_id
                index += 1
                break
            index += 1
        if can_id is None:
            return WarningEntry("asc", f"Skipped line without CAN ID: {stripped}", line_number)

        direction = None
        if index < len(tokens) and tokens[index] in {"Rx", "Tx"}:
            direction = tokens[index]
            index += 1

        if index >= len(tokens):
            return WarningEntry("asc", f"Skipped incomplete frame line: {stripped}", line_number)

        frame_type_token = tokens[index].lower()
        frame_type = "remote" if frame_type_token == "r" else "data"
        if frame_type_token in {"d", "r"}:
            index += 1
        else:
            marker_index = _find_token(tokens, {"d", "r"}, start=index)
            if marker_index is None:
                return WarningEntry("asc", f"Skipped line without frame marker: {stripped}", line_number)
            frame_type = "remote" if tokens[marker_index].lower() == "r" else "data"
            index = marker_index + 1

        if index >= len(tokens):
            return WarningEntry("asc", f"Skipped line without DLC: {stripped}", line_number)

        dlc = _parse_int_token(tokens[index])
        if dlc is None:
            return WarningEntry("asc", f"Skipped line with invalid DLC: {stripped}", line_number)
        index += 1

        data = _collect_data_bytes(tokens[index:], dlc)
        if data is None:
            return WarningEntry("asc", f"Skipped line with invalid payload: {stripped}", line_number)

        return CANFrame(
            timestamp=timestamp,
            can_id=can_id,
            dlc=dlc,
            data=data,
            channel=channel,
            direction=direction,
            frame_type=frame_type,
            source_line=line_number,
        )


class TrcParser(BaseTextLogParser):
    extensions = (".trc",)

    def parse_line(self, line: str, line_number: int) -> CANFrame | WarningEntry | None:
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            return None

        tokens = stripped.split()
        timestamp_index = None
        timestamp = None
        for index, token in enumerate(tokens):
            if token.endswith(")") and token[:-1].isdigit():
                continue
            maybe_timestamp = _parse_float_token(token.rstrip(")"))
            if maybe_timestamp is not None:
                timestamp_index = index
                timestamp = maybe_timestamp
                break
        if timestamp_index is None or timestamp is None:
            return WarningEntry("trc", f"Skipped malformed TRC line: {stripped}", line_number)

        direction_index = _find_token(tokens, {"Rx", "Tx"}, start=timestamp_index + 1)
        frame_marker_index = _find_token(tokens, {"d", "r"}, start=timestamp_index + 1)
        transport_marker_index = _find_token(tokens, {"DT", "FD"}, start=timestamp_index + 1)
        marker_index = frame_marker_index if frame_marker_index is not None else transport_marker_index
        if marker_index is None:
            return WarningEntry("trc", f"Skipped line without frame marker: {stripped}", line_number)

        channel, can_id = self._extract_channel_and_id(
            tokens,
            timestamp_index=timestamp_index,
            direction_index=direction_index,
            frame_marker_index=frame_marker_index,
        )
        if can_id is None:
            return WarningEntry("trc", f"Skipped line without CAN ID: {stripped}", line_number)

        direction = tokens[direction_index] if direction_index is not None else None
        marker = tokens[marker_index]
        frame_type = "remote" if marker.lower() == "r" else "data"
        if frame_marker_index is not None:
            dlc_index = frame_marker_index + 1
        elif direction_index is not None:
            dlc_index = direction_index + 1
        else:
            dlc_index = marker_index + 1
        if dlc_index >= len(tokens):
            return WarningEntry("trc", f"Skipped line without DLC: {stripped}", line_number)

        dlc = _parse_int_token(tokens[dlc_index])
        if dlc is None:
            return WarningEntry("trc", f"Skipped line with invalid DLC: {stripped}", line_number)

        data = _collect_data_bytes(tokens[dlc_index + 1 :], dlc)
        if data is None:
            return WarningEntry("trc", f"Skipped line with invalid payload: {stripped}", line_number)

        return CANFrame(
            timestamp=timestamp,
            can_id=can_id,
            dlc=dlc,
            data=data,
            channel=channel,
            direction=direction,
            frame_type=frame_type,
            source_line=line_number,
        )

    def _extract_channel_and_id(
        self,
        tokens: list[str],
        timestamp_index: int,
        direction_index: int | None,
        frame_marker_index: int | None,
    ) -> tuple[str | None, int | None]:
        stop_index_candidates = [
            index
            for index in (direction_index, frame_marker_index)
            if index is not None
        ]
        stop_index = min(stop_index_candidates) if stop_index_candidates else len(tokens)
        prefix_tokens = [
            token
            for token in tokens[timestamp_index + 1 : stop_index]
            if token not in {"DT", "FD"}
        ]

        channel: str | None = None
        can_id: int | None = None
        if len(prefix_tokens) >= 2 and prefix_tokens[0].isdigit():
            channel = prefix_tokens[0]
            candidate_tokens = prefix_tokens[1:]
        else:
            candidate_tokens = prefix_tokens

        for token in candidate_tokens:
            maybe_id = _parse_can_id(token)
            if maybe_id is not None:
                can_id = maybe_id
                break

        if can_id is None and channel is not None:
            maybe_id = _parse_can_id(channel)
            if maybe_id is not None:
                can_id = maybe_id
                channel = None

        return channel, can_id


class ParserRegistry:
    def __init__(self, parsers: list[LogParser] | None = None) -> None:
        self.parsers = parsers or [AscParser(), TrcParser()]

    def parser_for(self, path: str | Path) -> LogParser:
        suffix = Path(path).suffix.lower()
        for parser in self.parsers:
            if suffix in parser.extensions:
                return parser
        raise UnsupportedLogFormatError(f"Unsupported log format: {suffix or '<none>'}")

    def supported_extensions(self) -> tuple[str, ...]:
        extensions: list[str] = []
        for parser in self.parsers:
            extensions.extend(parser.extensions)
        return tuple(sorted(set(extensions)))


def _parse_float_token(token: str) -> float | None:
    try:
        return float(token)
    except ValueError:
        return None


def _parse_int_token(token: str) -> int | None:
    try:
        return int(token)
    except ValueError:
        return None


def _parse_can_id(token: str) -> int | None:
    normalized = token.rstrip("xX")
    if not HEX_ID_RE.match(token):
        return None
    try:
        return int(normalized, 16)
    except ValueError:
        return None


def _collect_data_bytes(tokens: list[str], dlc: int) -> bytes | None:
    if dlc == 0:
        return b""
    data_tokens = [token for token in tokens if BYTE_RE.match(token)]
    if len(data_tokens) < dlc:
        return None
    try:
        return bytes(int(token, 16) for token in data_tokens[:dlc])
    except ValueError:
        return None


def _find_token(tokens: list[str], values: set[str], start: int = 0) -> int | None:
    for index in range(start, len(tokens)):
        if tokens[index] in values:
            return index
    return None
