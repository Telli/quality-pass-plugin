#!/usr/bin/env python3
"""Install all linked skills or selected standalone copies without overwriting user edits."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from skill_packages import SKILLS, package_files

WINDOWS = os.name == "nt"


def owned_copy(destination, name):
    marker = destination / ".quality-pass-package.json"
    if not marker.is_file():
        return False
    metadata = json.loads(marker.read_text(encoding="utf-8"))
    if metadata.get("schema_version") != 1 or metadata.get("skill") != name:
        return False
    files = metadata.get("files", {})
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob("*")
              if (p.is_file() or p.is_symlink()) and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    if actual != set(files) | {marker.name}:
        return False
    return all(not (destination / p).is_symlink() and hashlib.sha256((destination / p).read_bytes()).hexdigest() == checksum for p, checksum in files.items())


def install(name, target, copy):
    if name not in {p.name for p in SKILLS.iterdir() if p.is_dir()}:
        raise ValueError(f"Unknown skill: {name}")
    source = SKILLS / name
    if not source.is_dir():
        raise ValueError(f"Unknown skill: {name}")
    destination = target / name
    existing = destination.exists() or destination.is_symlink()
    own_link = destination.is_symlink() and destination.resolve() == source.resolve()
    if existing and not own_link and (destination.is_symlink() or not owned_copy(destination, name)):
        raise ValueError(f"Preserving existing or modified skill: {destination}")
    if not copy:
        if existing and not own_link and not WINDOWS:
            raise ValueError(f"Existing copied skill requires --copy to refresh: {destination}")
        if own_link:
            print(f"already linked {name} -> {destination}")
            return
        if WINDOWS and existing:
            # A previous fallback copy remains refreshable without --copy.
            copy = True
        else:
            try:
                destination.symlink_to(source, target_is_directory=True)
                print(f"linked {name} -> {destination}")
                return
            except OSError:
                if not WINDOWS:
                    raise
                print("Symlink privilege unavailable; installing a standalone copy")
    with tempfile.TemporaryDirectory(prefix=".quality-pass-install-", dir=target) as temporary:
        staged = Path(temporary) / name
        staged.mkdir()
        for relative, data in package_files(name).items():
            path = staged / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if path.suffix in {".sh", ".py"}:
                path.chmod(0o755)
        backup = Path(temporary) / "previous"
        if existing:
            # rename() moves an own-link itself, never the checkout it points to.
            destination.rename(backup)
        try:
            staged.rename(destination)
        except OSError:
            if existing:
                backup.rename(destination)
            raise
    print(f"installed standalone {name} -> {destination}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--copy", action="store_true", help="install independently usable copies")
    parser.add_argument("--target", type=Path, default=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills")
    parser.add_argument("--skill", action="append", help="install selected standalone skills (repeatable; implies --copy)")
    args = parser.parse_args()
    errors = []
    try:
        args.target.mkdir(parents=True, exist_ok=True)
        for name in args.skill or sorted(p.name for p in SKILLS.iterdir() if p.is_dir()):
            try:
                install(name, args.target, args.copy or bool(args.skill))
            except (ValueError, OSError) as error:
                errors.append(str(error))
        if errors:
            for error in errors:
                print(f"install: {error}", file=sys.stderr)
            return 1
        print("Done. Reload the host's skills; invoke $quality-pass or an installed sub-skill.")
        return 0
    except (ValueError, OSError) as error:
        print(f"install: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
