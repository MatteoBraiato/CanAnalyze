from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from canalyze.services.parsers import AscParser, TrcParser


class ParserTests(unittest.TestCase):
    def test_asc_parser_normalizes_timestamps_and_keeps_warnings(self) -> None:
        content = "\n".join(
            [
                "date Thu Apr 08 08:00:00.000 2026",
                "base hex  timestamps absolute",
                "0.100000 1 123 Rx d 8 11 22 33 44 55 66 77 88",
                "malformed line",
                "0.250000 1 321 Tx d 2 AA BB",
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.asc"
            path.write_text(content, encoding="utf-8")

            result = AscParser().parse(path)

        self.assertEqual(len(result.frames), 2)
        self.assertAlmostEqual(result.frames[0].timestamp, 0.0)
        self.assertAlmostEqual(result.frames[1].timestamp, 0.15)
        self.assertEqual(result.frames[0].can_id, 0x123)
        self.assertEqual(result.frames[1].data, bytes([0xAA, 0xBB]))
        self.assertEqual(len(result.warnings), 1)

    def test_trc_parser_reads_vector_style_lines(self) -> None:
        content = "\n".join(
            [
                ";$FILEVERSION=1.1",
                ";$STARTTIME=0",
                "1) 0.500000 1 456 Rx d 8 01 02 03 04 05 06 07 08",
                "2) 0.750000 1 456 Rx d 1 09",
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.trc"
            path.write_text(content, encoding="utf-8")

            result = TrcParser().parse(path)

        self.assertEqual(len(result.frames), 2)
        self.assertAlmostEqual(result.frames[0].timestamp, 0.0)
        self.assertAlmostEqual(result.frames[1].timestamp, 0.25)
        self.assertEqual(result.frames[0].can_id, 0x456)
        self.assertEqual(result.frames[1].dlc, 1)

    def test_trc_parser_reads_dt_channel_id_layout(self) -> None:
        content = "\n".join(
            [
                ";$FILEVERSION=1.3",
                ";$STARTTIME=0",
                "1) 0.000000 DT 1 205 Rx d 8 11 22 33 44 55 66 77 88",
                "2) 0.100000 DT 1 206 Tx d 2 AA BB",
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample_dt.trc"
            path.write_text(content, encoding="utf-8")

            result = TrcParser().parse(path)

        self.assertEqual(len(result.frames), 2)
        self.assertEqual(result.frames[0].channel, "1")
        self.assertEqual(result.frames[0].can_id, 0x205)
        self.assertEqual(result.frames[1].can_id, 0x206)
        self.assertEqual(result.frames[1].data, bytes([0xAA, 0xBB]))

    def test_trc_parser_reads_pcan_view_layout(self) -> None:
        content = "\n".join(
            [
                ";$FILEVERSION=2.0",
                ";$STARTTIME=46119.5822671644",
                ";$COLUMNS=N,O,T,I,d,l,D",
                "      1         3.717 DT     028A Rx 2  00 00 ",
                "      2         4.264 DT     0383 Rx 8  00 00 00 00 00 00 00 00 ",
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pcan.trc"
            path.write_text(content, encoding="utf-8")

            result = TrcParser().parse(path)

        self.assertEqual(len(result.frames), 2)
        self.assertEqual(result.frames[0].can_id, 0x28A)
        self.assertEqual(result.frames[0].dlc, 2)
        self.assertEqual(result.frames[0].data, bytes([0x00, 0x00]))
        self.assertEqual(result.frames[1].can_id, 0x383)


if __name__ == "__main__":
    unittest.main()
