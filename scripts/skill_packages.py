"""Deterministic standalone distributions; all runtime resources stay inside each skill."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


def rewrite(text):
    for skill in sorted(SKILLS.iterdir(), key=lambda p: -len(p.name)):
        text = text.replace(f"../{skill.name}/SKILL.md", f"references/{skill.name}.md")
    return text.replace("../quality-pass/", "")


def package_files(name):
    if name not in {p.name for p in SKILLS.iterdir() if p.is_dir()}:
        raise ValueError(f"Unknown skill: {name}")
    source = SKILLS / name
    if not source.is_dir() or not (source / "SKILL.md").is_file():
        raise ValueError(f"Unknown skill: {name}")
    files = {}
    for base in (source, SKILLS / "quality-pass/references", SKILLS / "quality-pass/scripts"):
        for path in sorted(base.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            relative = path.relative_to(source).as_posix() if base == source else base.name + "/" + path.relative_to(base).as_posix()
            content = path.read_bytes()
            if path.suffix == ".md":
                content = rewrite(content.decode("utf-8")).encode("utf-8")
            files[relative] = content
    for skill in sorted(SKILLS.iterdir()):
        background = rewrite((skill / "SKILL.md").read_text(encoding="utf-8"))
        background = background.replace("](references/", "](").replace("](scripts/", "](../scripts/")
        files[f"references/{skill.name}.md"] = background.encode("utf-8")
    files["LICENSE"] = (ROOT / "LICENSE").read_bytes()
    # Ownership metadata makes copy refresh safe: reject changed or extra files.
    files[".quality-pass-package.json"] = (json.dumps({"schema_version": 1, "skill": name,
        "files": {p: hashlib.sha256(data).hexdigest() for p, data in sorted(files.items())}}, sort_keys=True, indent=2) + "\n").encode()
    return files


def write_package(name, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, content in sorted(package_files(name).items()):
            info = zipfile.ZipInfo(f"{name}/{path}", date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100755 if Path(path).suffix in {".sh", ".py"} else 0o100644) << 16
            archive.writestr(info, content)
    return destination


def validate_archive(archive_path):
    with tempfile.TemporaryDirectory(prefix="quality-pass-isolation-") as temp:
        root = Path(temp)
        with zipfile.ZipFile(archive_path) as archive:
            for name in archive.namelist():
                target = (root / name).resolve()
                if root not in target.parents or "\\" in name:
                    raise ValueError(f"Unsafe archive member: {name}")
            archive.extractall(root)
        skills = list(root.iterdir())
        if len(skills) != 1 or not (skills[0] / "SKILL.md").is_file():
            raise ValueError("Archive must contain exactly one skill directory")
        skill = skills[0]
        for path in skill.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            if "../quality-pass/" in text or re.search(r"\.\./quality-pass-[^/]+/", text):
                raise ValueError(f"Sibling dependency in {path.name}")
            for link in re.findall(r"\]\(([^)]+)\)", text):
                if "://" in link or link.startswith(("#", "mailto:")) or "<" in link:
                    continue
                target = (path.parent / link.split("#", 1)[0]).resolve()
                if target != skill and skill not in target.parents:
                    raise ValueError(f"Reference escapes standalone skill: {link}")
                if not target.exists():
                    raise ValueError(f"Missing standalone reference: {link}")
        for script in ("gate.py", "review.py"):
            subprocess.run([sys.executable, str(skill / "scripts" / script), "--help"], cwd=root, check=True, capture_output=True)
        # Run a real gate with no original checkout or sibling skills in the import path.
        fixture = root / "fixture"
        (fixture / ".quality-pass").mkdir(parents=True)
        (fixture / ".quality-pass/gates.json").write_text(json.dumps({"gates": [{"id": "isolation", "command": [sys.executable, "-c", "print('standalone gate works')"]}]}))
        subprocess.run([sys.executable, str(skill / "scripts/gate.py"), "--dir", str(fixture)], cwd=root, check=True, capture_output=True)
        return skill.name
