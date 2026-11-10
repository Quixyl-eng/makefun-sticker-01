#!/usr/bin/env python3
"""Write the make.fun sticker to /output/entry.png.

The sticker image ships beside this file as entry.png. The program only
copies those bytes: no drawing, no network, standard library only.
Both harness runs must produce identical output.
"""

from __future__ import annotations

import os
from pathlib import Path

ENTRY = Path(__file__).resolve().parent / "entry.png"


def main() -> None:
    out = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "entry.png").write_bytes(ENTRY.read_bytes())


if __name__ == "__main__":
    main()
