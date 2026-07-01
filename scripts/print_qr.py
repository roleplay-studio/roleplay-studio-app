"""CLI: print/save a QR code containing the server URL.

Usage:
    python -m app.print_qr                          # uses env PUBLIC_URL, prints to stdout + server-qr.png
    python -m app.print_qr --url https://my.host    # explicit URL
    python -m app.print_qr --out my-qr.png          # custom output path
"""

import argparse
import io
import os
import sys

import qrcode


def build_qr(url: str) -> "qrcode.QRCode":
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    return qr


def render_text(url: str) -> str:
    qr = build_qr(url)
    f = io.StringIO()
    qr.print_ascii(out=f)
    return f.getvalue()


def render_png(url: str) -> bytes:
    qr = build_qr(url)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate QR for server URL")
    parser.add_argument(
        "--url",
        default=os.getenv("PUBLIC_URL", "http://localhost:55245"),
        help="URL to encode (default: $PUBLIC_URL or http://localhost:55245)",
    )
    parser.add_argument(
        "--out",
        default="server-qr.png",
        help="Output PNG path (default: server-qr.png)",
    )
    args = parser.parse_args(argv)

    # Print ASCII to stdout
    print(render_text(args.url), file=sys.stdout)

    # Save PNG
    png = render_png(args.url)
    with open(args.out, "wb") as f:
        f.write(png)
    print(f"\nQR saved to: {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
