#!/usr/bin/env python3
"""Generate self-contained ZIPs and validate every archive in isolation."""
import argparse
import hashlib
from pathlib import Path
import sys

from skill_packages import SKILLS, validate_archive, write_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument("--skill", action="append", help="package selected skills (repeatable)")
    args = parser.parse_args()
    sums = []
    try:
        for name in args.skill or sorted(p.name for p in SKILLS.iterdir() if p.is_dir()):
            archive = write_package(name, args.output / f"{name}.zip")
            validate_archive(archive)
            sums.append(f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}")
            print(f"validated standalone archive: {archive}")
        (args.output / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
        return 0
    except (ValueError, OSError) as error:
        print(f"package: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
