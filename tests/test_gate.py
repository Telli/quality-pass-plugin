import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/quality-pass/scripts"
sys.path.insert(0, str(SCRIPTS))
import gate


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="quality pass ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".quality-pass").mkdir()

    def config(self, gates):
        (self.root / ".quality-pass/gates.json").write_text(json.dumps({"gates": gates}))

    def run_gate(self, *args, expected=0):
        result = subprocess.run([sys.executable, str(SCRIPTS / "gate.py"), "--dir", str(self.root), *args], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def latest(self):
        return json.loads((self.root / ".quality-pass/latest.json").read_text())

    def reporting_gate(self):
        code = "import pathlib,sys; pathlib.Path(sys.argv[1]).write_text(pathlib.Path('report-source.xml').read_text()); sys.exit(int(pathlib.Path('exit').read_text()))"
        self.config([{"id": "tests", "command": [sys.executable, "-c", code, "{report}"], "kind": "test", "report": {"format": "junit", "path": "{report}"}}])

    def report(self, failure="A", message="assert old", passed=1, exit_code=1):
        cases = ''.join(f'<testcase classname="suite" name="pass{i}" />' for i in range(passed))
        if failure:
            cases += f'<testcase classname="suite" name="{failure}"><failure message="{message}" /></testcase>'
        (self.root / "report-source.xml").write_text(f'<testsuite tests="{passed + bool(failure)}">{cases}</testsuite>')
        (self.root / "exit").write_text(str(exit_code))

    def test_different_failure_under_same_red_command_is_regression(self):
        self.reporting_gate()
        self.report("A")
        self.run_gate("--baseline", expected=1)
        self.report("B")
        result = self.run_gate(expected=1)
        self.assertIn("new or changed failures: suite::B", result.stdout)
        self.assertEqual(self.latest()["comparison"]["status"], "REGRESSION")

    def test_same_test_with_different_assertion_is_regression(self):
        self.reporting_gate()
        self.report()
        self.run_gate("--baseline", expected=1)
        self.report(message="assert new")
        self.run_gate(expected=1)
        self.assertEqual(self.latest()["comparison"]["status"], "REGRESSION")

    def test_equivalent_identified_failures_still_exit_one(self):
        self.reporting_gate()
        self.report()
        self.run_gate("--baseline", expected=1)
        self.run_gate(expected=1)
        self.assertEqual(self.latest()["comparison"]["status"], "EQUIVALENT")
        self.assertEqual(self.latest()["gates"][0]["evidence"]["counts"], {"total": 2, "passed": 1, "failed": 1, "skipped": 0})

    def test_unstructured_red_is_unknown(self):
        if not shutil.which("bash"):
            self.skipTest("Legacy shell gates require Bash")
        (self.root / ".quality-pass/gates").write_text(f'"{sys.executable}" -c "raise SystemExit(1)"\n')
        self.run_gate("--baseline", expected=1)
        result = self.run_gate(expected=1)
        self.assertIn("failure equivalence unknown", result.stdout)
        self.assertEqual(self.latest()["comparison"]["status"], "UNKNOWN")

    def test_fewer_tests_block_even_when_command_becomes_green(self):
        self.reporting_gate()
        self.report()
        self.run_gate("--baseline", expected=1)
        self.report(failure=None, passed=1, exit_code=0)
        self.run_gate(expected=1)
        self.assertEqual(self.latest()["comparison"]["status"], "REGRESSION")

    def test_old_report_is_not_accepted(self):
        self.report(failure=None, exit_code=0)
        self.config([{"id": "tests", "command": [sys.executable, "-c", "pass"], "kind": "test", "report": {"format": "junit", "path": "report-source.xml"}}])
        self.run_gate(expected=1)
        self.assertEqual(self.latest()["gates"][0]["status"], "ERROR")
        self.assertIn("predates", self.latest()["gates"][0]["evidence_error"])

    def test_zero_tests_and_malformed_report_are_not_green(self):
        self.reporting_gate()
        self.report(failure=None, passed=0, exit_code=0)
        self.run_gate(expected=1)
        self.assertEqual(self.latest()["gates"][0]["status"], "NO_TESTS")
        (self.root / "report-source.xml").write_text("broken XML")
        self.run_gate(expected=1)
        self.assertEqual(self.latest()["gates"][0]["status"], "ERROR")
        (self.root / "report-source.xml").write_text('<testsuite tests="1"><testcase name="disabled"><skipped /></testcase></testsuite>')
        self.run_gate(expected=1)
        self.assertEqual(self.latest()["gates"][0]["status"], "NO_TESTS")

    def test_missing_tools_distinguish_required_and_optional(self):
        self.config([{"id": "required", "command": ["quality-pass-missing-tool"]}, {"id": "optional", "command": ["quality-pass-missing-tool"], "optional": True}])
        self.run_gate(expected=1)
        self.assertEqual([g["status"] for g in self.latest()["gates"]], ["MISSING_TOOL", "SKIP"])

    def test_timeout(self):
        self.config([{"id": "slow", "command": [sys.executable, "-c", "import time;time.sleep(30)"], "timeout": 0.1}])
        start = time.monotonic()
        self.run_gate(expected=1)
        self.assertLess(time.monotonic() - start, 5)
        self.assertEqual(self.latest()["gates"][0]["status"], "TIMEOUT")

    def test_baseline_not_silently_overwritten_and_unique_logs(self):
        self.config([{"id": "check", "command": [sys.executable, "-c", "pass"]}])
        self.run_gate("--baseline")
        original = (self.root / ".quality-pass/baseline.json").read_bytes()
        self.run_gate("--baseline", expected=2)
        self.assertEqual((self.root / ".quality-pass/baseline.json").read_bytes(), original)
        self.run_gate()
        self.assertEqual(len(list((self.root / ".quality-pass/logs").iterdir())), 2)

    @patch.object(gate, "evaluated_test_project", return_value=None)
    def test_nested_dotnet_paths_and_multiple_projects(self, _evaluated):
        project = self.root / "services/with spaces"
        project.mkdir(parents=True)
        (project / "A.csproj").write_text("<Project />")
        (project / "B.csproj").write_text('<Project><ItemGroup><PackageReference Include="Microsoft.NET.Test.Sdk" /></ItemGroup></Project>')
        gates = gate.discover(self.root, [], 5)
        self.assertEqual(len(gates), 3)
        self.assertEqual(len({g["id"] for g in gates}), 3)
        self.assertEqual(gates[0]["cwd"], "services/with spaces")
        self.assertIn("A.csproj", gates[0]["command"])
        self.assertIn("--results-directory", gates[2]["command"])
        self.assertEqual(len(gate.discover(self.root, ["services/with spaces/B.csproj"], 5)), 2)

    @patch.object(gate, "evaluated_test_project", return_value=None)
    def test_dotnet_application_projects_get_no_structured_test_gate(self, _evaluated):
        (self.root / "Api.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk.Web" />')
        (self.root / "App.sln").write_text('Project("guid") = "Api", "Api.csproj", "guid"\n')
        gates = gate.discover(self.root, [], 5)
        self.assertEqual([g["id"] for g in gates], ["App.sln:build"])

    def test_dotnet_test_markers_from_sdk_quotes_and_imports_are_detected(self):
        (self.root / "Quoted").mkdir()
        (self.root / "Quoted/Quoted.csproj").write_text("<Project Sdk='MSTest.Sdk/3.6.1' />")
        (self.root / "tests").mkdir()
        (self.root / "tests/Directory.Build.props").write_text("<Project><PropertyGroup><IsTestProject>true</IsTestProject></PropertyGroup></Project>")
        (self.root / "tests/Inherited.csproj").write_text("<Project />")
        (self.root / "Imported").mkdir()
        (self.root / "test.props").write_text('<Project><ItemGroup><PackageReference Include="Microsoft.NET.Test.Sdk" /></ItemGroup></Project>')
        (self.root / "Imported/Imported.csproj").write_text("<Project><Import Project='../test.props' /></Project>")
        (self.root / "Dynamic").mkdir()
        (self.root / "Dynamic/Dynamic.csproj").write_text('<Project><Import Project="$(RepoRoot)/eng/x.props" /></Project>')
        with patch.object(gate, "evaluated_test_project", return_value=None):
            ids = {g["id"] for g in gate.discover(self.root, [], 5)}
        for name in ("Quoted/Quoted", "tests/Inherited", "Imported/Imported", "Dynamic/Dynamic"):
            self.assertIn(f"{name}.csproj:test", ids)

    def test_evaluated_msbuild_property_overrides_text_markers(self):
        (self.root / "shared.props").write_text("<Project><ItemGroup Condition=\"'$(IsTest)'=='true'\"><PackageReference Include=\"Microsoft.NET.Test.Sdk\" /></ItemGroup></Project>")
        (self.root / "Api.csproj").write_text('<Project><Import Project="shared.props" /></Project>')
        with patch.object(gate, "evaluated_test_project", return_value=False):
            self.assertEqual([g["id"] for g in gate.discover(self.root, [], 5)], ["Api.csproj:build"])
        with patch.object(gate, "evaluated_test_project", return_value=None):
            self.assertIn("Api.csproj:test", [g["id"] for g in gate.discover(self.root, [], 5)])

    def test_relative_executable_resolves_against_gate_cwd(self):
        script = self.root / "web/scripts/check.py"
        script.parent.mkdir(parents=True)
        script.write_text("#!/usr/bin/env python3\nprint('checked')\n")
        script.chmod(0o755)
        if os.name == "nt":
            self.skipTest("Shebang scripts are not directly executable on Windows")
        self.config([{"id": "check", "cwd": "web", "command": ["./scripts/check.py"]}])
        self.run_gate()
        self.assertEqual(self.latest()["gates"][0]["status"], "PASS")

    def test_nested_node_uses_workspace_manager_and_ignores_dependencies(self):
        (self.root / "package.json").write_text('{"packageManager":"pnpm@10.0.0"}')
        project = self.root / "packages/deep web"
        project.mkdir(parents=True)
        (project / "package.json").write_text('{"scripts":{"test":"runner","build":"build"}}')
        ignored = self.root / "node_modules/other"
        ignored.mkdir(parents=True)
        (ignored / "package.json").write_text('{"scripts":{"test":"bad"}}')
        gates = gate.discover(self.root, [], 5)
        self.assertEqual(len(gates), 2)
        self.assertEqual(gates[0]["command"], ["pnpm", "run", "test"])
        self.assertEqual(gates[0]["cwd"], "packages/deep web")

    def test_hash_character_in_shell_argument_is_preserved(self):
        if not shutil.which("bash"):
            self.skipTest("Legacy shell gates require Bash")
        (self.root / ".quality-pass/gates").write_text("printf '%s' '#value'\n")
        self.run_gate()
        self.assertEqual(Path(self.latest()["gates"][0]["log"]).read_text(), "#value")

    def test_jest_trx_and_go_failure_identities(self):
        path = self.root / "report"
        path.write_text(json.dumps({"numTotalTests": 1, "testResults": [{"name": "tests.js", "assertionResults": [{"fullName": "reject cross tenant", "status": "failed", "failureMessages": ["expected 403"]}]}]}))
        self.assertIn("tests.js::reject cross tenant", gate.parse_report([path], "jest")["failures"])
        path.write_text('<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010"><TestDefinitions><UnitTest id="random" name="Reject"><TestMethod className="Auth" /></UnitTest></TestDefinitions><Results><UnitTestResult testId="random" outcome="Failed"><Output><ErrorInfo><Message>expected 403</Message></ErrorInfo></Output></UnitTestResult></Results></TestRun>')
        self.assertIn("Auth::Reject", gate.parse_report([path], "trx")["failures"])
        path.write_text('\n'.join(json.dumps(e) for e in [{"Package": "auth", "Test": "Reject", "Action": "output", "Output": "expected 403"}, {"Package": "auth", "Test": "Reject", "Action": "fail"}]))
        self.assertIn("auth::Reject", gate.parse_report([path], "go")["failures"])

    def test_incomplete_structured_reports_cannot_prove_equivalence(self):
        path = self.root / "report"
        path.write_text('<testsuite tests="1" failures="1"><testcase classname="suite" name="A" /></testsuite>')
        with self.assertRaisesRegex(ValueError, "failures totals"):
            gate.parse_report([path], "junit")
        path.write_text(json.dumps({"Action": "fail", "Package": "broken"}))
        with self.assertRaisesRegex(ValueError, "package failures"):
            gate.parse_report([path], "go")
        path.write_text("[]")
        with self.assertRaisesRegex(ValueError, "Jest report structure"):
            gate.parse_report([path], "jest")
        path.write_text('<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010"><ResultSummary><Counters total="2" /></ResultSummary></TestRun>')
        with self.assertRaisesRegex(ValueError, "TRX total"):
            gate.parse_report([path], "trx")

    def test_configuration_changes_and_unknown_assertion_details_are_unknown(self):
        self.reporting_gate()
        self.report(message="")
        self.run_gate("--baseline", expected=1)
        self.run_gate(expected=1)
        self.assertEqual(self.latest()["comparison"]["status"], "UNKNOWN")
        config = json.loads((self.root / ".quality-pass/gates.json").read_text())
        config["gates"][0]["timeout"] = 10
        self.config(config["gates"])
        self.run_gate(expected=1)
        self.assertEqual(self.latest()["comparison"]["status"], "UNKNOWN")

    def test_invalid_configuration_and_empty_discovery(self):
        self.run_gate(expected=2)
        self.config([{"command": [sys.executable, "-c", "pass"], "optional": "false"}])
        self.run_gate(expected=2)
        self.config([{"command": [sys.executable, "-c", "pass"], "cwd": "../outside"}])
        self.run_gate(expected=2)
        self.config([{"command": [sys.executable, "-c", "pass"], "timeout": float("nan")}])
        self.run_gate(expected=2)
        self.assertFalse(self.latest()["gates"])
        (self.root / "README.md").write_text("not a project")
        self.run_gate("--project", "README.md", expected=2)

    @patch.object(gate, "evaluated_test_project", return_value=None)
    def test_solution_members_are_not_duplicated(self, _evaluated):
        (self.root / "Tests.csproj").write_text("<Project><PropertyGroup><IsTestProject>true</IsTestProject></PropertyGroup></Project>")
        (self.root / "App.sln").write_text('Project("guid") = "Tests", "Tests.csproj", "guid"\n')
        gates = gate.discover(self.root, [], 5)
        self.assertEqual(len(gates), 2)
        self.assertEqual(gates[0]["command"][2], "App.sln")


if __name__ == "__main__":
    unittest.main()
