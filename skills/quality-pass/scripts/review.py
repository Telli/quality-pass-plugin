#!/usr/bin/env python3
"""Persist review scope, reproducible findings, approvals, and gated progress."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fnmatch
import json
import os
from pathlib import Path
import sys

from common import commit, contained, digest, file_hash, git, source_fingerprint, write_json

STATUSES = {"suspected", "demonstrated", "rejected", "needs-reverification"}
DIMENSIONS = {"slop", "bugs", "security", "performance", "dead-code", "architecture"}


def now():
    return datetime.now(timezone.utc).isoformat()


def tracked_files(root):
    return [p for p in git(root, "ls-files", "-z").decode().split("\0") if p]


def selected_files(root, selectors):
    files = tracked_files(root)
    selected = set()
    for selector in selectors:
        contained(root, selector)
        matches = [p for p in files if p == selector or p.startswith(selector.rstrip("/") + "/") or fnmatch.fnmatchcase(p, selector)]
        if not matches:
            raise ValueError(f"File selection matched no tracked paths: {selector}")
        selected.update(matches)
    return sorted(selected)


def scope(root, args):
    current = commit(root)
    if not current:
        raise ValueError("Review scope requires a Git checkout with a commit")
    files = set(selected_files(root, args.files))
    base_commit = None
    if args.base:
        base_commit = git(root, "merge-base", args.base, "HEAD").decode().strip()
        files.update(p for p in git(root, "diff", "--name-only", "-z", base_commit, "HEAD").decode().split("\0") if p)
        files.update(p for p in git(root, "diff", "--name-only", "-z", "HEAD").decode().split("\0") if p)
    if args.feature and not (args.files or args.base):
        raise ValueError("Resolve the feature to explicit --files or --base before recording its scope")
    mode = args.mode or ("standard" if args.files or args.base else "full")
    if mode == "full" or not (args.files or args.base):
        files.update(tracked_files(root))
    dimensions = ["bugs", "security"] if mode == "quick" else sorted(DIMENSIONS)
    return {"reviewed_commit": current, "source_fingerprint": source_fingerprint(root), "base": args.base,
            "base_commit": base_commit, "feature": args.feature, "mode": mode, "files": sorted(files),
            "dimensions": dimensions, "coverage": {
                "quick": "Selected changes plus direct callers, tests, authorization boundaries, and contracts; other dimensions not reviewed",
                "standard": "All six dimensions within selected changes and affected callers, tests, authorization boundaries, and contracts; unrelated code excluded",
                "full": "All six dimensions across the repository; record any unread areas and unrun measurements",
            }[mode], "created_at": now()}


def new_state(root):
    return {"schema_version": 1, "reviewed_commit": commit(root), "scope": None, "findings": {}, "gate_results": [], "history": []}


def load_state(root):
    path = root / ".quality-pass/state.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else new_state(root)
    if state.get("schema_version") != 1:
        raise ValueError("Unsupported review state version")
    return state


@contextmanager
def state_lock(root):
    directory = root / ".quality-pass"
    directory.mkdir(exist_ok=True)
    path = directory / "state.lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("Review state is locked; check for an active writer before removing a stale state.lock")
    try:
        os.close(fd)
        yield
    finally:
        path.unlink()


def event(state, action, id_=None, **details):
    state["history"].append({"at": now(), "action": action, "finding_id": id_, **details})


def watched(root, files):
    snapshots = {}
    for path in sorted(set(files)):
        resolved = contained(root, path)
        raw = root / path
        snapshots[path] = digest({"path": str(resolved), "content": file_hash(resolved),
                                  "symlink": os.readlink(raw) if raw.is_symlink() else None})
    return snapshots


def refresh(root, state):
    for id_, finding in state["findings"].items():
        if finding["watched"] != watched(root, finding["watched"]):
            if finding["verification"]["status"] != "needs-reverification":
                finding["verification"]["status"] = "needs-reverification"
                finding["approved"] = False
                finding["disposition"] = "open"
                event(state, "invalidate", id_, reason="Relevant files changed")


def record(root, state, data):
    for field in ("dimension", "title", "file", "anchor", "verification"):
        if field not in data or not data[field]:
            raise ValueError(f"Finding requires {field}")
    if data["dimension"] not in DIMENSIONS:
        raise ValueError("Unknown review dimension")
    verification = data["verification"]
    if not isinstance(verification, dict) or verification.get("status") not in STATUSES:
        raise ValueError("Finding requires a valid verification status")
    if not verification.get("evidence") or not verification.get("observed_result"):
        raise ValueError("Each finding requires verification evidence and an observed result, including rejected claims")
    if verification["status"] == "demonstrated" and (not verification.get("validation_commands") or not verification.get("reproduction")):
        raise ValueError("Demonstrated findings require reproduction steps and validation commands")
    id_ = "QP-" + digest({"dimension": data["dimension"], "file": data["file"], "anchor": data["anchor"]})[:12]
    previous = state["findings"].get(id_)
    files = [data["file"], *data.get("related_files", [])]
    snapshot = watched(root, files)
    # Repeated unchanged claims retain approval/dismissal and do not create duplicate history.
    if previous and previous["watched"] == snapshot and previous["verification"] == verification:
        return id_
    finding = {**data, "id": id_, "reviewed_commit": commit(root), "watched": snapshot,
               "approved": False, "disposition": "dismissed" if verification["status"] == "rejected" else "open",
               "updated_at": now(), "completed_fixes": previous.get("completed_fixes", []) if previous else []}
    state["findings"][id_] = finding
    event(state, "record", id_, verification_status=verification["status"])
    return id_


def approve(state, ids):
    for id_ in ids:
        finding = state["findings"].get(id_)
        if not finding or finding["verification"]["status"] != "demonstrated" or finding["disposition"] != "open":
            raise ValueError(f"Only open, demonstrated findings may be approved: {id_}")
    for id_ in ids:
        state["findings"][id_]["approved"] = True
        event(state, "approve", id_)


def complete(root, state, args):
    finding = state["findings"].get(args.id)
    # Changes made to fix an approved finding are expected here; do not refresh before completion.
    if not finding or not finding["approved"] or finding["verification"]["status"] != "demonstrated":
        raise ValueError("Completion requires an approved, demonstrated finding; re-verify stale findings first")
    if finding["disposition"] == "completed":
        raise ValueError("Finding is already completed; inspect saved history rather than recording it twice")
    result = json.loads(Path(args.gate_result).read_text(encoding="utf-8"))
    if result.get("schema_version") != 1 or not result.get("gates"):
        raise ValueError("Completion requires a gate result with executed gates")
    if (result.get("root") != str(root) or result.get("commit") != commit(root)
            or not result.get("source_fingerprint") or result["source_fingerprint"] != source_fingerprint(root)
            or result.get("source_changed_during_run")):
        raise ValueError("Gate result is stale or belongs to another checkout; rerun gates")
    if any(g["status"] not in {"PASS", "SKIP"} for g in result["gates"]):
        raise ValueError("Completion requires passing gates; unresolved failures are not completed fixes")
    if result.get("comparison", {}).get("status") in {"REGRESSION", "UNKNOWN"}:
        raise ValueError("Baseline comparison is not verified; resolve it before completion")
    fix_commit = git(root, "rev-parse", "--verify", args.fix_commit + "^{commit}").decode().strip()
    if fix_commit != commit(root):
        raise ValueError("Fix commit must be current HEAD, with gates run after committing")
    if git(root, "diff", "--name-only", "HEAD", "--", *finding["watched"]).strip():
        raise ValueError("Relevant fix files have uncommitted edits")
    finding["disposition"] = "completed"
    finding["watched"] = watched(root, finding["watched"])
    finding["completed_fixes"].append({"commit": fix_commit, "gate_result": args.gate_result, "completed_at": now()})
    state["gate_results"].append({"finding_id": args.id, "result": result})
    event(state, "complete", args.id, commit=fix_commit)
    refresh(root, state)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=".")
    commands = parser.add_subparsers(dest="command", required=True)
    selection = commands.add_parser("scope", help="record branch/diff/file/feature scope and coverage")
    selection.add_argument("--base")
    selection.add_argument("--files", action="append", default=[])
    selection.add_argument("--feature")
    selection.add_argument("--mode", choices=["quick", "standard", "full"])
    entry = commands.add_parser("record", help="record a finding JSON document")
    entry.add_argument("--input", required=True)
    approval = commands.add_parser("approve", help="record approval already given by the user")
    approval.add_argument("ids", nargs="+")
    completion = commands.add_parser("complete")
    completion.add_argument("id")
    completion.add_argument("--fix-commit", required=True)
    completion.add_argument("--gate-result", default=".quality-pass/latest.json")
    commands.add_parser("status", help="invalidate changed findings and show saved progress")
    args = parser.parse_args(argv)
    root = Path(args.dir).resolve()
    try:
        with state_lock(root):
            state = load_state(root)
            if args.command != "complete":
                refresh(root, state)
            if args.command == "scope":
                state["scope"] = scope(root, args)
                state["reviewed_commit"] = state["scope"]["reviewed_commit"]
                event(state, "scope", mode=state["scope"]["mode"])
                output = state["scope"]
            elif args.command == "record":
                data = json.loads(Path(args.input).read_text(encoding="utf-8"))
                output = {"id": record(root, state, data)}
            elif args.command == "approve":
                approve(state, args.ids)
                output = {"approved_findings": args.ids}
            elif args.command == "complete":
                # Resolve relative result paths against the selected repository.
                args.gate_result = str(contained(root, args.gate_result))
                complete(root, state, args)
                output = {"completed": args.id}
            else:
                output = state
            write_json(root / ".quality-pass/state.json", state)
            print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"review: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
