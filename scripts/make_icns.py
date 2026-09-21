"""Generate the macOS .icns application icon from a PNG logo.

macOS `.app` bundles need an `.icns` icon, and the repository only ships `.png`
and `.ico`. PyInstaller can convert a PNG on the fly, but only when Pillow is
installed; generating the icon once here and committing it keeps the build free
of any converter.

The container is written directly (big-endian header + PNG chunks), so this works
on Windows and Linux — no macOS-only `iconutil` / `sips` required.

Usage:
    py scripts/make_icns.py                       # window_logo.png -> window_logo.icns
    py scripts/make_icns.py --padding 0           # no extra margin
    py scripts/make_icns.py --source start_logo.png --output start_logo.icns

Requires Pillow (a transitive dependency of matplotlib).
"""

import argparse
import io
import struct
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent

# ICNS element types carrying PNG data, paired with the pixel size macOS expects.
# Several slots share a pixel size: the 1x and 2x variants of one slot are stored
# under different type codes.
_PNG_ELEMENTS = (
    ("icp4", 16),  # 16x16
    ("icp5", 32),  # 32x32
    ("ic11", 32),  # 16x16@2x
    ("ic12", 64),  # 32x32@2x
    ("ic07", 128),  # 128x128
    ("ic13", 256),  # 128x128@2x
    ("ic08", 256),  # 256x256
    ("ic14", 512),  # 256x256@2x
    ("ic09", 512),  # 512x512
    ("ic10", 1024),  # 512x512@2x
)

# Apple's icon grid leaves a margin around the artwork; a source image that fills
# its canvas edge-to-edge looks oversized in the Dock without one.
_DEFAULT_PADDING = 0.08


def _squared(image: Image.Image, padding: float) -> Image.Image:
    """Centre *image* on a transparent square canvas with a relative margin."""
    side = max(image.size)
    pad = int(round(side * padding))
    canvas = Image.new("RGBA", (side + 2 * pad, side + 2 * pad), (0, 0, 0, 0))
    canvas.paste(
        image,
        (pad + (side - image.size[0]) // 2, pad + (side - image.size[1]) // 2),
    )
    return canvas


def build_icns(source: Path, padding: float = _DEFAULT_PADDING) -> bytes:
    """Return the bytes of an .icns holding *source* at every standard size."""
    image = Image.open(source).convert("RGBA")
    canvas = _squared(image, padding)

    body = b""
    for element_type, size in _PNG_ELEMENTS:
        buffer = io.BytesIO()
        canvas.resize((size, size), Image.LANCZOS).save(buffer, format="PNG")
        payload = buffer.getvalue()
        # Chunk length includes the 8-byte type+length header itself.
        body += element_type.encode("ascii") + struct.pack(">I", len(payload) + 8) + payload

    return b"icns" + struct.pack(">I", len(body) + 8) + body


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default="window_logo.png",
        help="PNG to derive the icon from (default: window_logo.png)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output .icns path (default: the source name with .icns)",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=_DEFAULT_PADDING,
        help=f"Transparent margin as a fraction of the width (default: {_DEFAULT_PADDING})",
    )
    args = parser.parse_args()

    source = Path(args.source)
    if not source.is_absolute():
        source = REPO_ROOT / source
    output = Path(args.output) if args.output else source.with_suffix(".icns")
    if not output.is_absolute():
        output = REPO_ROOT / output

    image = Image.open(source)
    data = build_icns(source, args.padding)
    output.write_bytes(data)

    print(f"Source : {source} ({image.size[0]}x{image.size[1]}, {image.mode})")
    print(f"Output : {output}")
    print(f"Size   : {len(data) / 1024:.0f} KB")
    print(f"Sizes  : {', '.join(str(size) for _type, size in _PNG_ELEMENTS)}")
    if max(image.size) < 1024:
        print(
            f"Note   : the source is only {max(image.size)}px wide, so the 1024px "
            "entries are upscaled. A 1024x1024 source would render sharper."
        )


if __name__ == "__main__":
    main()
