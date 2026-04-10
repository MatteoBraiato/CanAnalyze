from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


ICON_SIZES = [
    (16, 16),
    (20, 20),
    (24, 24),
    (32, 32),
    (40, 40),
    (48, 48),
    (64, 64),
    (128, 128),
    (256, 256),
]


def build_icon(source: Path, output: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"PNG icon source was not found at '{source}'.")

    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        rgba = image.convert("RGBA")
        rgba.save(output, format="ICO", sizes=ICON_SIZES)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Windows .ico file from a PNG source.")
    parser.add_argument("--source", required=True, help="Path to the PNG source icon.")
    parser.add_argument("--output", required=True, help="Path to the output .ico file.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    build_icon(Path(args.source), Path(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
