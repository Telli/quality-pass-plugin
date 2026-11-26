#!/usr/bin/env python3
"""Generate Codex and Gemini CLI reviewer agents and Gemini commands from agents/qp-*.md.

agents/*.md (Claude Code format) is the source of truth; hosts/models.json maps its model tier
to each host's model. Run after editing either; CI runs --check.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
HOSTS = ROOT / "hosts"
MARKER = "quality-pass generated file: edit agents/ or hosts/models.json, then run scripts/build-host-agents.py"
READ_ONLY = ("You are a read-only reviewer: never edit, create, or delete project files, and never commit. "
             "Shell use is limited to inspection (git log/show/grep, builds into a temporary directory, test runs).")
GEMINI_TOOLS = ["read_file", "read_many_files", "grep_search", "glob", "list_directory", "run_shell_command"]
COMMANDS = {
    "run": ("quality-pass", "Full quality pass: baseline, reviews, verify, plan, approval, gated fixes"),
    "review": ("quality-pass-review", "Review only: ranked, evidence-backed report with no code changes"),
    "execute": ("quality-pass-execute", "Execute an approved quality-pass report, one gated commit per phase"),
    "dead-code": ("quality-pass-dead-code", "Two-pattern verified dead-code deletion sweep"),
    "gate": ("quality-pass-gate", "Run typecheck/lint/tests/build and report verbatim"),
}


def parse_agent(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path.name}: missing frontmatter")
    header, body = text[4:].split("\n---\n", 1)
    fields = {}
    for line in header.splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip("\"'")
    for key in ("name", "description", "model", "effort"):
        if not fields.get(key):
            raise ValueError(f"{path.name}: frontmatter needs {key}")
    fields["body"] = body.strip() + "\n"
    return fields


def toml_string(value):
    return json.dumps(value, ensure_ascii=False)


def toml_multiline(value):
    if '"""' in value:
        raise ValueError("agent body cannot contain triple quotes")
    return '"""\n' + value.replace("\\", "\\\\") + '"""'


def codex_agent(agent, models):
    model = models["codex"].get(agent["model"])
    effort = models["codex"]["effort"].get(agent["effort"])
    lines = [f"# {MARKER}", f"name = {toml_string(agent['name'].replace('-', '_'))}",
             f"description = {toml_string(agent['description'])}"]
    if model:
        lines.append(f"model = {toml_string(model)}")
    if effort:
        lines.append(f"model_reasoning_effort = {toml_string(effort)}")
    lines.append(f"developer_instructions = {toml_multiline(READ_ONLY + chr(10) + chr(10) + agent['body'])}")
    return "\n".join(lines) + "\n"


def gemini_agent(agent, models):
    model = models["gemini"].get(agent["model"]) or "inherit"
    # Gemini's loader rejects unknown keys and non-Gemini tool names, so only its own fields appear here.
    header = [f"name: {agent['name']}", f"description: {toml_string(agent['description'])}", "kind: local",
              "tools: [" + ", ".join(GEMINI_TOOLS) + "]", f"model: {model}", "max_turns: 60", "timeout_mins: 20"]
    return "---\n" + "\n".join(header) + f"\n---\n\n<!-- {MARKER} -->\n\n{READ_ONLY}\n\n{agent['body']}"


def gemini_command(skill, description):
    prompt = (f"Activate the `{skill}` skill (activate_skill) and follow it exactly, including its iron rules. "
              "For reviewer dimensions, delegate to the qp-* subagents when they are available. "
              "User request: {{args}}")
    return f"# {MARKER}\ndescription = {toml_string(description)}\nprompt = {toml_string(prompt)}\n"


def generate():
    models = json.loads((HOSTS / "models.json").read_text(encoding="utf-8"))
    files = {}
    for path in sorted((ROOT / "agents").glob("qp-*.md")):
        agent = parse_agent(path)
        files[f"codex/agents/{agent['name'].replace('-', '_')}.toml"] = codex_agent(agent, models)
        files[f"gemini/agents/{agent['name']}.md"] = gemini_agent(agent, models)
    for command, (skill, description) in COMMANDS.items():
        files[f"gemini/commands/quality-pass/{command}.toml"] = gemini_command(skill, description)
    return files


def write_files(files, root):
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        # Bytes keep LF endings on every OS; Path.write_text(newline=) needs Python 3.10+.
        path.write_bytes(content.encode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if generated files are stale")
    args = parser.parse_args()
    files = generate()
    generated_dirs = [HOSTS / "codex", HOSTS / "gemini"]
    existing = {p.relative_to(HOSTS).as_posix() for d in generated_dirs if d.exists() for p in d.rglob("*") if p.is_file()}
    stale = sorted(existing - set(files)) + sorted(p for p, c in files.items()
                                                    if not (HOSTS / p).is_file() or (HOSTS / p).read_text(encoding="utf-8") != c)
    if args.check:
        if stale:
            print("host agents are stale; run scripts/build-host-agents.py: " + ", ".join(stale), file=sys.stderr)
            return 1
        print("host agents up to date")
        return 0
    for relative in sorted(existing - set(files)):
        (HOSTS / relative).unlink()
    write_files(files, HOSTS)
    print(f"wrote {len(files)} host files under {HOSTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
