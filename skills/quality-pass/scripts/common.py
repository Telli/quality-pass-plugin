"""Shared helpers copied into every standalone skill package."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors="replace").strip() or "Git operation failed")
    return result.stdout


def commit(root):
    try:
        return git(root, "rev-parse", "--verify", "HEAD").decode().strip()
    except (ValueError, FileNotFoundError):
        return None


def file_hash(path):
    if path.is_symlink():
        return digest({"link": os.readlink(path)})
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_fingerprint(root):
    try:
        change = hashlib.sha256(git(root, "diff", "--binary", "HEAD")).hexdigest()
        paths = git(root, "ls-files", "--others", "--exclude-standard", "-z").decode().split("\0")
        caches = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
        untracked = {p: file_hash(root / p) for p in paths if p and p.split("/")[0] not in {".quality-pass", ".agents"}
                     and not caches.intersection(Path(p).parts)}
        configuration = {name: file_hash(root / ".quality-pass" / name) for name in ("gates", "gates.json")}
        return digest({"commit": commit(root), "changes": change, "untracked": untracked, "gate_configuration": configuration})
    except (ValueError, FileNotFoundError):
        return None


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def contained(root, relative):
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"Path escapes repository: {relative}")
    return path
