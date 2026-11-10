# make.fun sticker

A contest entry for [make.fun's sticker bounty](https://make.fun/bounty/makefun-sticker-01).
The image is a 1024×1024 die-cut style badge: a robot on a 1-2-3 podium,
navy and cyan, made to read clearly at sticker size.

## Layout

- `main.py` — validates the shipped image and copies it to the judge path
- `entry.png` — the sticker itself (PNG, 1024×1024, under 1 MiB)
- `LICENSE` — MIT, copyright Quixyl-eng

## How the program works

The judge runs `main.py` in a fresh Python 3.13 container with no network
and nothing installed beyond the standard library. The repository is
mounted read-only; the program must write `/output/entry.png`. The
harness also honours `MAKEFUN_OUTPUT_DIR` when that variable is set.

`main.py` does not redraw the sticker. It reads `entry.png` next to the
script, checks that the bytes are a complete PNG or JPEG within the
contest limits (at most 1024×1024 and 1 MiB), then copies those same
bytes to the output path. Two runs must produce identical files, which
a straight copy guarantees.

## Local run

```bash
python3 main.py --check -v
mkdir -p /tmp/sticker-out
MAKEFUN_OUTPUT_DIR=/tmp/sticker-out python3 main.py -v
# or:
python3 main.py --output-dir /tmp/sticker-out --verbose
```

`--check` validates the source and prints a short report without writing
output. `--source` and `--output-dir` override the default paths.
`--json` prints the same report as a single JSON object, including the
SHA-256 digest once the validator has computed it.

## Limits the program enforces

- File name of the output is always `entry.png`
- Format is PNG or JPEG, detected by magic bytes
- At most 1 MiB (1048576 bytes) and at most 1024×1024 pixels
- The file must be complete: PNG chunks through IEND with valid CRCs,
  or JPEG segments through the end-of-image marker
