#!/usr/bin/env python3
"""Run gates and conservatively compare current-run structured failure evidence."""
import argparse
from datetime import datetime, timezone
import glob
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

from common import commit, contained, digest, source_fingerprint, write_json

IGNORED = {".git", ".agents", ".quality-pass", "node_modules", "vendor", ".venv", "venv", "dist", "build", "bin", "obj", "target", "__pycache__"}


def walk_manifests(root):
    files = []
    for directory, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED and not (Path(directory) / d).is_symlink())
        for name in sorted(names):
            if name in {"package.json", "Cargo.toml", "go.mod", "pyproject.toml", "setup.py", "requirements.txt"} or name.endswith((".sln", ".slnx", ".csproj", ".fsproj", ".vbproj")):
                files.append(Path(directory) / name)
    return files


TEST_MARKERS = re.compile(r"Microsoft\.NET\.Test\.Sdk|MSTest\.Sdk|<IsTestProject>\s*true\s*</IsTestProject>", re.IGNORECASE)


def evaluated_test_project(path):
    """Ask MSBuild (conditions applied, no restore needed); None when the SDK can't answer."""
    if not shutil.which("dotnet"):
        return None
    try:
        result = subprocess.run(["dotnet", "msbuild", path.name, "-nologo", "-getProperty:IsTestProject", "-getItem:PackageReference"],
                                cwd=path.parent, capture_output=True, text=True, timeout=120)
        data = json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    # Microsoft.NET.Test.Sdk only sets IsTestProject after restore, so its evaluated reference counts too.
    references = {str(item.get("Identity", "")).lower() for item in data.get("Items", {}).get("PackageReference", []) if isinstance(item, dict)}
    return data.get("Properties", {}).get("IsTestProject", "").lower() == "true" or "microsoft.net.test.sdk" in references


def is_dotnet_test_project(path, root):
    """Prefer evaluated MSBuild; otherwise only a project with no test markers anywhere it imports is non-test."""
    evaluated = evaluated_test_project(path)
    if evaluated is not None:
        return evaluated
    sources = [path] + [d / name for d in [path.parent, *path.parent.parents] if d == root or root in d.parents
                        for name in ("Directory.Build.props", "Directory.Build.targets") if (d / name).is_file()]
    seen = set()
    while sources:
        source = sources.pop()
        if source in seen:
            continue
        seen.add(source)
        try:
            text = source.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            return True
        if TEST_MARKERS.search(text):
            return True
        for target in re.findall(r"<Import\b[^>]*\bProject\s*=\s*[\"']([^\"']+)[\"']", text, re.IGNORECASE):
            if "$(" in target or "*" in target:
                return True  # unresolvable import; keep the test gate
            sources.append((source.parent / target.replace("\\", "/")).resolve())
    return False


def discover(root, projects, timeout):
    root = Path(root).resolve()
    files = []
    for selection in projects or ["."]:
        path = contained(root, selection)
        if not path.exists():
            raise ValueError(f"Project does not exist: {selection}")
        files.extend([path] if path.is_file() else walk_manifests(path))
    files = sorted(set(files))
    gates, seen = [], set()

    def add(path, name, command, report=None, optional=False, kind=None, requires=None):
        cwd = path.parent.relative_to(root).as_posix()
        key = (cwd, tuple(command))
        if key not in seen:
            seen.add(key)
            gates.append({"id": f"{path.relative_to(root).as_posix()}:{name}", "cwd": cwd, "command": command, "timeout": float(timeout),
                          "report": report, "optional": optional, "kind": kind, "requires": requires or []})

    members, solution_members = set(), {}
    for path in files:
        if path.suffix == ".sln":
            refs = re.findall(r'"([^"\n]+\.(?:cs|fs|vb)proj)"', path.read_text(encoding="utf-8-sig"))
            solution_members[path] = {(path.parent / ref.replace("\\", "/")).resolve() for ref in refs}
        elif path.suffix == ".slnx":
            solution_members[path] = {(path.parent / node.attrib["Path"].replace("\\", "/")).resolve() for node in ET.parse(path).iter("Project") if "Path" in node.attrib}
    for refs in solution_members.values():
        members.update(refs)
    for path in files:
        directory = path.parent
        if path.name == "package.json":
            package = json.loads(path.read_text(encoding="utf-8"))
            pm = "npm"
            for ancestor in [directory, *directory.parents]:
                if ancestor != root and root not in ancestor.parents:
                    break
                pkg = ancestor / "package.json"
                pin = json.loads(pkg.read_text(encoding="utf-8")).get("packageManager", "") if pkg.exists() else ""
                if pin:
                    pm = pin.split("@", 1)[0]
                    if pm not in {"npm", "pnpm", "yarn", "bun"}:
                        raise ValueError(f"Unsupported packageManager: {pin}")
                    break
                locks = {"pnpm-lock.yaml": "pnpm", "yarn.lock": "yarn", "bun.lock": "bun", "bun.lockb": "bun", "package-lock.json": "npm"}
                match = next((tool for lock, tool in locks.items() if (ancestor / lock).exists()), None)
                if match:
                    pm = match
                    break
            scripts = package.get("scripts", {})
            for name in ("typecheck", "type-check", "lint", "test", "build"):
                if name == "type-check" and "typecheck" in scripts:
                    continue
                if name in scripts:
                    add(path, name, [pm, "run", name], kind="test" if name == "test" else None)
            if not any(n in scripts for n in ("typecheck", "type-check")) and (directory / "tsconfig.json").exists():
                compiler = directory / "node_modules/.bin/tsc"
                if os.name == "nt":
                    compiler = compiler.with_suffix(".cmd")
                add(path, "typecheck", [str(compiler), "--noEmit", "-p", "tsconfig.json"])
        elif path.suffix in {".sln", ".slnx", ".csproj", ".fsproj", ".vbproj"}:
            if path.resolve() in members:
                continue
            add(path, "build", ["dotnet", "build", path.name, "--nologo"])
            # Application projects produce no TRX; only attach a structured test gate where tests exist.
            tests = solution_members[path] if path in solution_members else {path}
            if not any(is_dotnet_test_project(member, root) for member in tests):
                continue
            add(path, "test", ["dotnet", "test", path.name, "--nologo", "--no-build", "--logger", "trx", "--results-directory", "{report_dir}"],
                {"format": "trx", "path": "{report_dir}/*.trx"}, kind="test")
        elif path.name == "Cargo.toml":
            add(path, "build", ["cargo", "build", "--all-targets"])
            add(path, "clippy", ["cargo", "clippy", "--all-targets", "--", "-D", "warnings"], optional=True, requires=["cargo-clippy"])
            add(path, "test", ["cargo", "test"], kind="test")
        elif path.name == "go.mod":
            add(path, "vet", ["go", "vet", "./..."])
            add(path, "build", ["go", "build", "./..."])
            add(path, "test", ["go", "test", "-json", "./..."], {"format": "go", "path": "{log}"}, kind="test")
        else:
            if path.name not in {"pyproject.toml", "setup.py", "requirements.txt"}:
                raise ValueError(f"Unsupported project manifest: {path.relative_to(root)}")
            add(path, "ruff", ["ruff", "check", "."], optional=True)
            if (directory / "mypy.ini").exists():
                add(path, "mypy", ["mypy", "."], optional=True)
            add(path, "test", ["pytest", "-q", "--junitxml={report}"], {"format": "junit", "path": "{report}"}, kind="test")
    return gates


def load_gates(root, args):
    json_path, shell_path = root / ".quality-pass/gates.json", root / ".quality-pass/gates"
    if args.project:
        return discover(root, args.project, args.timeout), "selected projects"
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("gates"), list):
            raise ValueError("gates.json must contain a gates array")
        gates = []
        for i, gate in enumerate(data["gates"]):
            if not isinstance(gate, dict):
                raise ValueError("Each gate must be an object")
            command = gate.get("command")
            if not isinstance(command, (str, list)) or not command or (isinstance(command, list) and not all(isinstance(x, str) and x for x in command)):
                raise ValueError("Gate command must be a nonempty shell string or argv array")
            timeout = gate.get("timeout", args.timeout)
            if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
                raise ValueError("Gate timeout must be positive")
            cwd = gate.get("cwd", ".")
            if not isinstance(cwd, str) or not contained(root, cwd).is_dir():
                raise ValueError(f"Invalid gate working directory: {cwd}")
            report = gate.get("report")
            if report is not None and (not isinstance(report, dict) or report.get("format") not in {"junit", "trx", "jest", "go"} or not isinstance(report.get("path"), str)):
                raise ValueError("Report requires a supported format and path")
            if not isinstance(gate.get("optional", False), bool) or not isinstance(gate.get("requires", []), list) or not all(isinstance(x, str) and x for x in gate.get("requires", [])):
                raise ValueError("optional must be boolean and requires must be an array of tool names")
            gates.append({"id": gate.get("id", f"gate-{i + 1}"), "command": command, "cwd": cwd, "timeout": float(timeout),
                          "optional": gate.get("optional", False), "kind": gate.get("kind"), "report": report, "requires": gate.get("requires", [])})
        ids = [g["id"] for g in gates]
        if not all(isinstance(x, str) and x for x in ids) or len(set(ids)) != len(ids):
            raise ValueError("Gate IDs must be nonempty and unique")
        return gates, "gates.json"
    if shell_path.exists():
        commands = [line.strip() for line in shell_path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
        return [{"id": f"gate-{i + 1}", "command": c, "cwd": ".", "timeout": args.timeout,
                 "optional": False, "kind": None, "report": None, "requires": []} for i, c in enumerate(commands)], "gates"
    return discover(root, [], args.timeout), "auto-detected"


def parse_report(paths, format_):
    counts = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
    failures, identities = {}, set()
    complete_details = True

    def add(identity, outcome, detail=""):
        nonlocal complete_details
        if not identity or identity == "::" or identity in identities:
            raise ValueError(f"Missing or duplicate test identity: {identity}")
        identities.add(identity)
        counts["total"] += 1
        counts[outcome] += 1
        if outcome == "failed":
            failures[identity] = digest(detail)
            complete_details &= bool(detail) and (not isinstance(detail, dict) or any(detail.values()))

    for path in paths:
        if format_ in {"junit", "trx"}:
            tree = ET.parse(path)
            if format_ == "junit":
                for case in tree.iter("testcase"):
                    failure = case.find("failure")
                    if failure is None:
                        failure = case.find("error")
                    outcome = "failed" if failure is not None else "skipped" if case.find("skipped") is not None else "passed"
                    identity = "::".join([case.get("classname", case.get("file", "")), case.get("name", "")])
                    detail = {"type": failure.get("type", ""), "message": failure.get("message", ""), "text": failure.text or ""} if failure is not None else ""
                    add(identity, outcome, detail)
                for suite in tree.iter("testsuite"):
                    cases = list(suite.iter("testcase"))
                    actual = {"tests": len(cases), "failures": sum(c.find("failure") is not None for c in cases),
                              "errors": sum(c.find("error") is not None for c in cases), "skipped": sum(c.find("skipped") is not None for c in cases)}
                    for field, value in actual.items():
                        if field in suite.attrib and int(suite.get(field)) != value:
                            raise ValueError(f"JUnit {field} totals disagree with testcase results")
            else:
                ns = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
                file_counts = dict(counts)
                definitions = {}
                for test in tree.findall(".//t:UnitTest", ns):
                    method = test.find("t:TestMethod", ns)
                    definitions[test.get("id")] = "::".join([method.get("className", "") if method is not None else "", test.get("name", "")])
                for case in tree.findall(".//t:UnitTestResult", ns):
                    outcome = case.get("outcome")
                    if outcome not in {"Passed", "Failed", "NotExecuted"}:
                        raise ValueError(f"Unsupported TRX outcome: {outcome}")
                    error = case.find("t:Output/t:ErrorInfo", ns)
                    add(definitions.get(case.get("testId"), case.get("testName", "")), {"Passed": "passed", "Failed": "failed", "NotExecuted": "skipped"}[outcome],
                        ET.tostring(error, encoding="unicode") if error is not None else "")
                counters = tree.find(".//t:ResultSummary/t:Counters", ns)
                if counters is not None:
                    for field, category in {"total": "total", "passed": "passed", "failed": "failed", "notExecuted": "skipped"}.items():
                        if field in counters.attrib and int(counters.get(field)) != counts[category] - file_counts[category]:
                            raise ValueError(f"TRX {field} totals disagree with result identities")
        elif format_ == "jest":
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("testResults", []), list) or not all(isinstance(suite, dict) for suite in data.get("testResults", [])):
                raise ValueError("Invalid Jest report structure")
            if data.get("wasInterrupted") or data.get("numRuntimeErrorTestSuites", 0):
                raise ValueError("Jest report contains interrupted or unidentified suite failures")
            count_before = counts["total"]
            for suite in data.get("testResults", []):
                if not isinstance(suite.get("assertionResults", []), list) or not all(isinstance(case, dict) for case in suite.get("assertionResults", [])):
                    raise ValueError("Invalid Jest assertion results")
                if suite.get("message") and not suite.get("assertionResults"):
                    raise ValueError("Report contains unidentified suite errors")
                for case in suite.get("assertionResults", []):
                    outcome = case.get("status")
                    if outcome not in {"passed", "failed", "pending", "todo", "disabled"}:
                        raise ValueError(f"Unsupported Jest outcome: {outcome}")
                    add(f"{suite.get('name', '')}::{case.get('fullName', '')}", outcome if outcome in {"passed", "failed"} else "skipped", case.get("failureMessages", []))
            if counts["total"] - count_before != data.get("numTotalTests", counts["total"] - count_before):
                raise ValueError("Jest test totals disagree with assertion results")
        elif format_ == "go":
            details, failed_packages, failed_tests = {}, set(), set()
            for line in path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("Invalid Go report event")
                identity = f"{event.get('Package', '')}::{event.get('Test', '')}"
                if event.get("Action") == "output" and event.get("Test"):
                    output = event.get("Output", "")
                    if not output.startswith(("=== RUN", "--- PASS", "--- FAIL", "--- SKIP")):
                        details.setdefault(identity, []).append(output)
                if event.get("Test") and event.get("Action") in {"pass", "fail", "skip"}:
                    add(identity, {"pass": "passed", "fail": "failed", "skip": "skipped"}[event["Action"]], details.get(identity, []))
                    if event["Action"] == "fail":
                        failed_tests.add(event.get("Package"))
                elif event.get("Action") == "fail":
                    failed_packages.add(event.get("Package"))
            if failed_packages - failed_tests:
                raise ValueError("Go report contains unidentified package failures")
    return {"format": format_, "counts": counts, "failures": failures, "identities": sorted(identities), "complete_failure_details": complete_details}


def stop_process(process):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
    if os.name != "nt":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def find_bash():
    bash = shutil.which("bash")
    if os.name != "nt":
        return bash or "bash"
    system = Path(os.environ.get("SystemRoot", r"C:\Windows")).resolve()
    if bash and system not in Path(bash).resolve().parents:
        return bash
    # System32\bash.exe is the WSL launcher; prefer Git for Windows' bash.
    candidates = []
    git_exe = shutil.which("git")
    if git_exe:
        candidates += [Path(git_exe).resolve().parents[1] / "bin/bash.exe", Path(git_exe).resolve().parents[1] / "usr/bin/bash.exe"]
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"), os.environ.get("LOCALAPPDATA")):
        if base:
            candidates += [Path(base) / "Git/bin/bash.exe", Path(base) / "Programs/Git/bin/bash.exe"]
    return next((str(c) for c in candidates if c.is_file()), bash or "bash")


def locate(tool, cwd):
    # Path-like commands run relative to the gate cwd, not the runner's directory.
    if os.path.isabs(tool) or "/" in tool or (os.sep in tool):
        return shutil.which(str(Path(tool) if os.path.isabs(tool) else cwd / tool))
    return shutil.which(tool)


def run_gate(root, gate, directory, index):
    log = directory / f"{index}.log"
    report_dir = directory / f"{index}-reports"
    report_dir.mkdir()
    substitutions = {"report": str(report_dir / "report.xml"), "report_dir": str(report_dir), "log": str(log), "python": sys.executable}
    def expand(value):
        for key, replacement in substitutions.items():
            value = value.replace("{" + key + "}", replacement)
        return value
    command = gate["command"]
    argv = [find_bash(), "-o", "pipefail", "-c", expand(command)] if isinstance(command, str) else [expand(part) for part in command]
    cwd = root / gate["cwd"]
    if os.name == "nt" and not isinstance(command, str):
        tool = locate(argv[0], cwd)
        if tool and tool.lower().endswith((".cmd", ".bat")):
            argv = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", subprocess.list2cmdline(argv)]
    result = {"id": gate["id"], "command": command, "cwd": gate["cwd"], "log": str(log), "optional": gate["optional"], "evidence": None}
    start = time.monotonic()
    patterns, before = [], {}
    if gate["report"]:
        pattern = Path(expand(gate["report"]["path"]))
        if not pattern.is_absolute():
            pattern = root / gate["cwd"] / pattern
        contained(root, str(pattern))
        patterns = [str(pattern)]
        for path in glob.glob(str(pattern)):
            stat = Path(path).stat()
            before[path] = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
    missing = [tool for tool in [argv[0], *gate["requires"]] if locate(tool, cwd) is None]
    if missing:
        result.update(status="SKIP" if gate["optional"] else "MISSING_TOOL", exit_code=None, reason="Missing tool: " + ", ".join(missing))
        log.write_text(result["reason"] + "\n", encoding="utf-8")
    else:
        with log.open("w", encoding="utf-8") as stream:
            process = subprocess.Popen(argv, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, env=dict(os.environ, CI="true"),
                start_new_session=os.name != "nt", creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
            try:
                code = process.wait(timeout=gate["timeout"])
                result.update(status="PASS" if code == 0 else "MISSING_TOOL" if code == 127 else "FAIL", exit_code=code)
            except subprocess.TimeoutExpired:
                stop_process(process)
                result.update(status="TIMEOUT", exit_code=None, reason=f"Exceeded {gate['timeout']}s")
            except KeyboardInterrupt:
                stop_process(process)
                raise
        if patterns:
            paths = [Path(p) for pattern in patterns for p in sorted(glob.glob(pattern))]
            fresh = []
            for path in paths:
                contained(root, str(path))
                stat = path.stat()
                if before.get(str(path)) == (stat.st_mtime_ns, stat.st_size, stat.st_ino):
                    result["evidence_error"] = "Report predates the current run"
                    break
                fresh.append(path)
            else:
                try:
                    if not fresh:
                        raise ValueError("No current-run report found")
                    result["evidence"] = parse_report(fresh, gate["report"]["format"])
                except (ValueError, ET.ParseError, OSError, TypeError) as error:
                    result["evidence_error"] = str(error)
            if result["evidence"] and result["evidence"]["counts"]["total"] == result["evidence"]["counts"]["skipped"]:
                result.update(status="NO_TESTS", reason="Structured report contains zero executed tests")
            elif result["evidence"] and result["status"] == "PASS" and result["evidence"]["counts"]["failed"]:
                result.update(status="FAIL", reason="Report contains failures despite a successful command")
        if gate["report"] and result.get("evidence_error") and result["status"] == "PASS":
            result.update(status="ERROR", reason=result["evidence_error"])
    result["duration_seconds"] = round(time.monotonic() - start, 3)
    return result


def compare(baseline, current):
    if baseline.get("schema_version") != 1 or baseline.get("configuration_hash") != current["configuration_hash"]:
        return {"status": "UNKNOWN", "details": ["gate configuration changed or baseline format unsupported; failure equivalence unknown"]}
    previous = {g["id"]: g for g in baseline["gates"]}
    details = []
    regression = unknown = improved = False
    for gate in current["gates"]:
        old = previous.get(gate["id"])
        if not old:
            unknown = True
            details.append(f"{gate['id']}: missing baseline; failure equivalence unknown")
            continue
        evidence, prior = gate.get("evidence"), old.get("evidence")
        if evidence and prior:
            now_counts, old_counts = evidence["counts"], prior["counts"]
            if now_counts["total"] - now_counts["skipped"] < old_counts["total"] - old_counts["skipped"]:
                regression = True
                details.append(f"{gate['id']}: executed test count decreased")
        if gate["status"] == "PASS":
            improved |= old["status"] != "PASS"
            continue
        if gate["status"] == old["status"] == "SKIP":
            details.append(f"{gate['id']}: optional gate skipped; unverified")
            continue
        if gate["status"] == "FAIL" and old["status"] == "PASS":
            regression = True
            details.append(f"{gate['id']}: new failing gate")
        elif (gate["status"] == old["status"] == "FAIL" and gate.get("exit_code") == old.get("exit_code") == 1
              and evidence and prior and evidence["failures"] and prior["failures"]
              and evidence.get("complete_failure_details") and prior.get("complete_failure_details")):
            changed = [identity for identity, signature in evidence["failures"].items() if prior["failures"].get(identity) != signature]
            if changed:
                regression = True
                details.append(f"{gate['id']}: new or changed failures: {', '.join(changed)}")
            else:
                details.append(f"{gate['id']}: identified failures match baseline")
                improved |= len(evidence["failures"]) < len(prior["failures"])
        else:
            unknown = True
            details.append(f"{gate['id']}: failure equivalence unknown")
    return {"status": "REGRESSION" if regression else "UNKNOWN" if unknown else "IMPROVED" if improved else "EQUIVALENT", "details": details}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=".", help="repository root")
    parser.add_argument("--baseline", action="store_true", help="save baseline.json and baseline.txt")
    parser.add_argument("--replace-baseline", action="store_true", help="explicitly replace an existing baseline")
    parser.add_argument("--print", action="store_true", dest="print_only")
    parser.add_argument("--project", action="append", default=[], help="select project file or directory (repeatable)")
    parser.add_argument("--timeout", type=float, default=600.0, help="per-gate timeout in seconds (default: 600)")
    args = parser.parse_args(argv)
    root = Path(args.dir).resolve()
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError("Timeout must be positive")
        if args.replace_baseline and not args.baseline:
            raise ValueError("--replace-baseline requires --baseline")
        gates, source = load_gates(root, args)
        if not gates:
            raise ValueError("No gates found; define .quality-pass/gates.json or .quality-pass/gates")
        baseline_path = root / ".quality-pass/baseline.json"
        if args.baseline and baseline_path.exists() and not args.replace_baseline and not args.print_only:
            raise ValueError("Baseline already exists; use --baseline --replace-baseline deliberately")
        print(f"== quality-pass gate  root={root}  source={source}")
        for gate in gates:
            print(f"  [{gate['id']}] {gate['command']} (cwd={gate['cwd']}, timeout={gate['timeout']}s)")
        if args.print_only:
            return 0
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        directory = root / ".quality-pass/logs" / stamp
        directory.mkdir(parents=True)
        result = {"schema_version": 1, "root": str(root), "commit": commit(root), "source_fingerprint": source_fingerprint(root),
                  "configuration": gates, "configuration_hash": digest(gates), "created_at": stamp, "gates": []}
        for index, gate in enumerate(gates, 1):
            outcome = run_gate(root, gate, directory, index)
            result["gates"].append(outcome)
            print(f"  {outcome['status']} {outcome['duration_seconds']}s {gate['id']}  log: {outcome['log']}")
            if outcome.get("evidence"):
                print("  tests: " + ", ".join(f"{key}={value}" for key, value in outcome["evidence"]["counts"].items()))
                if outcome["evidence"]["failures"]:
                    print("  failure identities: " + ", ".join(outcome["evidence"]["failures"]))
            elif gate["kind"] == "test":
                print("  test counts and failure identities unavailable")
            if outcome["status"] != "PASS":
                print("".join(Path(outcome["log"]).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)[-40:]), end="")
            if outcome.get("evidence_error"):
                print(f"  evidence unavailable: {outcome['evidence_error']}")
        if result["source_fingerprint"] != source_fingerprint(root):
            result["source_changed_during_run"] = True
            print("  WARNING: repository changed during gate execution")
        summary = "\n".join(f"  {g['status']}  {g['duration_seconds']}s  {g['command']}" for g in result["gates"]) + "\n"
        (directory / "summary.txt").write_text(summary, encoding="utf-8")
        print("== summary\n" + summary, end="")
        if args.baseline:
            write_json(baseline_path, result)
            (root / ".quality-pass/baseline.txt").write_text(summary, encoding="utf-8")
            print(f"  baseline saved at commit {result['commit'] or 'unknown'}")
        elif baseline_path.exists():
            result["comparison"] = compare(json.loads(baseline_path.read_text(encoding="utf-8")), result)
            print(f"== vs baseline: {result['comparison']['status']}")
            for detail in result["comparison"]["details"]:
                print("  " + detail)
        elif (root / ".quality-pass/baseline.txt").exists():
            result["comparison"] = {"status": "UNKNOWN", "details": ["Legacy text baseline: failure equivalence unknown"]}
            print("  Legacy text baseline: failure equivalence unknown")
        write_json(directory / "results.json", result)
        write_json(root / ".quality-pass/latest.json", result)
        return int(any(g["status"] not in {"PASS", "SKIP"} for g in result["gates"]) or result.get("comparison", {}).get("status") == "REGRESSION" or result.get("source_changed_during_run", False))
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError) as error:
        print(f"gate: {error}", file=sys.stderr)
        if not args.print_only:
            # A failed invocation must not leave an old green result at latest.json.
            try:
                write_json(root / ".quality-pass/latest.json", {"schema_version": 1, "root": str(root), "commit": commit(root), "gates": [], "error": str(error)})
            except OSError:
                pass
        return 2
    except KeyboardInterrupt:
        print("gate: interrupted; rerun before accepting results", file=sys.stderr)
        write_json(root / ".quality-pass/latest.json", {"schema_version": 1, "root": str(root), "gates": [], "error": "Interrupted"})
        return 130


if __name__ == "__main__":
    sys.exit(main())
