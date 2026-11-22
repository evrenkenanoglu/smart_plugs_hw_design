"""Optional relative cable-coupling study; never predicts compliance levels."""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        help="future, revision-matched cable/source/enclosure model configuration",
    )
    parser.parse_args()
    parser.exit(
        2,
        "Cable study is deferred: no evidence-based cable, enclosure, source, "
        "termination, or validated model configuration is available. No field "
        "or emissions result was generated.\n",
    )


if __name__ == "__main__":
    raise SystemExit(main())
