"""Backward-compat shim — print_qr moved to ``scripts/print_qr.py`` (m17).

Run via ``python -m scripts.print_qr`` or ``python -m app.print_qr``
(the latter delegates to the former).
"""

from scripts.print_qr import main

if __name__ == "__main__":
    raise SystemExit(main())
