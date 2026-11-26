#!/usr/bin/env python3
"""Install quality-pass user-wide for Claude Code, Codex, Gemini CLI, and Antigravity CLI.

User-level locations make the skills and reviewer agents available in every project:
  claude       plugin `quality-pass@quality-pass-marketplace`, user scope (via the `claude` CLI)
  codex        skills -> ~/.agents/skills, agents -> $CODEX_HOME/agents (~/.codex/agents)
  gemini       skills -> ~/.agents/skills, agents -> ~/.gemini/agents, commands -> ~/.gemini/commands/quality-pass
  antigravity  skills -> ~/.gemini/antigravity-cli/skills
Existing files you changed and unrelated files are never overwritten.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HOSTS = ("claude", "codex", "gemini", "antigravity")
MANIFEST = ".quality-pass-installed.json"
MARKETPLACE = "quality-pass-marketplace"
PLUGIN = f"quality-pass@{MARKETPLACE}"
GITHUB_SOURCE = "telli/quality-pass-plugin"

sys.path.insert(0, str(Path(__file__).resolve().parent))
_spec = importlib.util.spec_from_file_location("install_codex", Path(__file__).resolve().parent / "install-codex.py")
skills_installer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(skills_installer)
generator_spec = importlib.util.spec_from_file_location("build_host_agents", Path(__file__).resolve().parent / "build-host-agents.py")
generator = importlib.util.module_from_spec(generator_spec)
generator_spec.loader.exec_module(generator)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def install_files(files, target):
    """Write generated files into target; refresh only files this installer wrote and nobody changed."""
    target.mkdir(parents=True, exist_ok=True)
    manifest_path = target / MANIFEST
    try:
        owned = json.loads(manifest_path.read_text(encoding="utf-8")).get("files", {})
    except (OSError, ValueError):
        owned = {}
    errors, record = [], {}
    for name, content in sorted(files.items()):
        data = content.encode("utf-8")
        path = target / name
        if path.is_symlink() or path.is_dir():
            errors.append(f"Preserving existing {path}")
            continue
        if path.exists():
            current = digest(path.read_bytes())
            if current == digest(data):
                record[name] = current
                continue
            if owned.get(name) != current:
                errors.append(f"Preserving existing or modified file: {path}")
                if name in owned:
                    record[name] = owned[name]
                continue
        path.write_bytes(data)
        record[name] = digest(data)
        print(f"installed {path}")
    for name, recorded in owned.items():
        path = target / name
        if name not in files and path.is_file() and digest(path.read_bytes()) == recorded:
            path.unlink()
            print(f"removed retired {path}")
    if record:
        manifest_path.write_text(json.dumps({"schema_version": 1, "files": record}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return errors


def host_files(prefix):
    return {path[len(prefix):]: content for path, content in generator.generate().items() if path.startswith(prefix)}


def install_skills(target, copy, done):
    if target.resolve() in done:
        return []
    done.add(target.resolve())
    target.mkdir(parents=True, exist_ok=True)
    errors = []
    for name in sorted(p.name for p in skills_installer.SKILLS.iterdir() if p.is_dir()):
        try:
            skills_installer.install(name, target, copy)
        except (ValueError, OSError) as error:
            errors.append(str(error))
    return errors


def run(command):
    print("$ " + " ".join(command))
    result = subprocess.run(command, capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip()
    if output:
        print(output)
    return result.returncode, output


def install_claude(source, explicit):
    claude = shutil.which("claude")
    commands = [["claude", "plugin", "marketplace", "add", source], ["claude", "plugin", "install", PLUGIN, "--scope", "user"]]
    if not claude:
        message = "claude CLI not found; run:\n  " + "\n  ".join(" ".join(c) for c in commands)
        return [message] if explicit else (print("skip claude: " + message) or [])
    code, output = run([claude] + commands[0][1:])
    already = "already" in output.lower()
    if code != 0 and not already:
        return ["claude marketplace add failed"]
    if already and run([claude, "plugin", "marketplace", "update", MARKETPLACE])[0] != 0:
        return ["claude marketplace update failed"]
    code, output = run([claude] + commands[1][1:])
    if code != 0 and "already" not in output.lower():
        return ["claude plugin install failed"]
    if "already" in output.lower() and run([claude, "plugin", "update", PLUGIN, "--scope", "user"])[0] != 0:
        return ["claude plugin update failed"]
    return []


def detected(home):
    found = set()
    for host, marker, cli in (("claude", ".claude", "claude"), ("codex", ".codex", "codex"),
                              ("gemini", ".gemini", "gemini"), ("antigravity", ".gemini/antigravity-cli", "agy")):
        if shutil.which(cli) or (home / marker).exists():
            found.add(host)
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", action="append", choices=HOSTS + ("all",),
                        help="host to install for (repeatable). Default: every host detected on this machine")
    parser.add_argument("--copy", action="store_true", help="install standalone skill copies instead of links to this checkout")
    parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    parser.add_argument("--skills-target", type=Path, help="shared Agent Skills directory (default ~/.agents/skills)")
    parser.add_argument("--claude-source", default=GITHUB_SOURCE,
                        help=f"marketplace source for Claude Code (default {GITHUB_SOURCE}; use 'local' for this checkout)")
    args = parser.parse_args()
    home = args.home
    codex_home = Path(os.environ["CODEX_HOME"]) if os.environ.get("CODEX_HOME") and args.home == Path.home() else home / ".codex"
    explicit = set(args.host or [])
    hosts = set(HOSTS) if "all" in explicit else (explicit or detected(home))
    if not hosts:
        print("No supported host detected; pass --host claude|codex|gemini|antigravity|all", file=sys.stderr)
        return 2
    shared = args.skills_target or home / ".agents/skills"
    errors, done = [], set()
    if "claude" in hosts:
        source = str(ROOT) if args.claude_source == "local" else args.claude_source
        errors += install_claude(source, "claude" in explicit or "all" in explicit)
    if "codex" in hosts:
        errors += install_skills(shared, args.copy, done)
        errors += install_files(host_files("codex/agents/"), codex_home / "agents")
    if "gemini" in hosts:
        errors += install_skills(shared, args.copy, done)
        errors += install_files(host_files("gemini/agents/"), home / ".gemini/agents")
        errors += install_files(host_files("gemini/commands/quality-pass/"), home / ".gemini/commands/quality-pass")
    if "antigravity" in hosts:
        errors += install_skills(home / ".gemini/antigravity-cli/skills", args.copy, done)
    for error in errors:
        print(f"install: {error}", file=sys.stderr)
    print("Installed for: " + ", ".join(sorted(hosts)) + ("" if not errors else " (with errors above)"))
    print("Restart open sessions. Claude: /quality-pass:quality-pass  Codex: $quality-pass  Gemini: /quality-pass:run")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
