import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "skills/quality-pass/scripts/review.py"
GATE = ROOT / "skills/quality-pass/scripts/gate.py"


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        (self.root / "auth.py").write_text("def allowed(): return True\n")
        (self.root / "caller.py").write_text("from auth import allowed\n")
        (self.root / ".gitignore").write_text(".quality-pass/\ninput.json\n")
        self.git("add", ".")
        self.git("commit", "-m", "baseline")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.DEVNULL).decode().strip()

    def run_review(self, *args, expected=0):
        result = subprocess.run([sys.executable, str(REVIEW), "--dir", str(self.root), *args], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout) if result.returncode == 0 else result.stderr

    def finding(self, status="demonstrated"):
        data = {"dimension": "security", "title": "Missing tenant check", "file": "auth.py", "anchor": "allowed",
                "related_files": ["caller.py"], "verification": {"status": status, "evidence": "allowed returns True",
                "observed_result": "Tenant B reaches Tenant A data", "reproduction": ["Call allowed with tenant B"], "validation_commands": ["python test_auth.py"]}}
        (self.root / "input.json").write_text(json.dumps(data))
        return data

    def record(self, status="demonstrated"):
        self.finding(status)
        return self.run_review("record", "--input", str(self.root / "input.json"))["id"]

    def test_changed_branch_scope_and_file_selection(self):
        self.git("checkout", "-b", "feature")
        (self.root / "auth.py").write_text("def allowed(): return False\n")
        self.git("add", "auth.py")
        self.git("commit", "-m", "change")
        scope = self.run_review("scope", "--base", "main", "--mode", "quick")
        self.assertEqual(scope["files"], ["auth.py"])
        self.assertEqual(scope["dimensions"], ["bugs", "security"])
        self.assertEqual(scope["reviewed_commit"], self.git("rev-parse", "HEAD"))
        scope = self.run_review("scope", "--files", "caller.py", "--feature", "authorization", "--mode", "standard")
        self.assertEqual(scope["files"], ["caller.py"])
        self.assertEqual(len(scope["dimensions"]), 6)

    def test_feature_needs_explicit_boundaries_and_invalid_base_fails(self):
        self.assertIn("explicit", self.run_review("scope", "--feature", "auth", expected=2))
        self.run_review("scope", "--base", "unknown", expected=2)

    def test_stable_ids_preserve_approval_and_dismissal(self):
        id_ = self.record()
        self.run_review("approve", id_)
        self.assertEqual(self.record(), id_)
        state = self.run_review("status")
        self.assertTrue(state["findings"][id_]["approved"])
        self.assertEqual(len([e for e in state["history"] if e["action"] == "record"]), 1)
        rejected = self.record("rejected")
        self.assertEqual(rejected, id_)
        self.assertEqual(self.run_review("status")["findings"][id_]["disposition"], "dismissed")

    def test_related_code_change_invalidates_approval(self):
        id_ = self.record()
        self.run_review("approve", id_)
        (self.root / "caller.py").write_text("changed contract\n")
        finding = self.run_review("status")["findings"][id_]
        self.assertFalse(finding["approved"])
        self.assertEqual(finding["verification"]["status"], "needs-reverification")
        self.run_review("approve", id_, expected=2)

    def test_suspected_cannot_be_approved_and_demonstrated_needs_reproduction(self):
        id_ = self.record("suspected")
        self.run_review("approve", id_, expected=2)
        data = self.finding()
        del data["verification"]["reproduction"]
        (self.root / "input.json").write_text(json.dumps(data))
        self.run_review("record", "--input", str(self.root / "input.json"), expected=2)

    def test_completion_requires_fresh_passing_gate_and_records_fix(self):
        id_ = self.record()
        self.run_review("approve", id_)
        (self.root / "auth.py").write_text("def allowed(): return False\n")
        self.git("add", "auth.py")
        self.git("commit", "-m", "fix")
        config = {"gates": [{"id": "check", "command": [sys.executable, "-c", "from auth import allowed;assert not allowed()"]}]}
        (self.root / ".quality-pass/gates.json").write_text(json.dumps(config))
        subprocess.check_call([sys.executable, str(GATE), "--dir", str(self.root)], stdout=subprocess.DEVNULL)
        self.run_review("complete", id_, "--fix-commit", "HEAD")
        state = self.run_review("status")
        self.assertEqual(state["findings"][id_]["disposition"], "completed")
        self.assertEqual(len(state["gate_results"]), 1)
        (self.root / "caller.py").write_text("changed\n")
        self.run_review("complete", id_, "--fix-commit", "HEAD", expected=2)

    def test_existing_lock_and_escape_are_rejected(self):
        (self.root / ".quality-pass").mkdir()
        (self.root / ".quality-pass/state.lock").write_text("owned by another process")
        self.assertIn("locked", self.run_review("status", expected=2))
        (self.root / ".quality-pass/state.lock").unlink()
        self.run_review("scope", "--files", "../outside", expected=2)

    def test_stale_gate_and_changed_configuration_cannot_complete(self):
        id_ = self.record()
        self.run_review("approve", id_)
        path = self.root / ".quality-pass/gates.json"
        path.write_text(json.dumps({"gates": [{"id": "check", "command": [sys.executable, "-c", "pass"]}]}))
        subprocess.check_call([sys.executable, str(GATE), "--dir", str(self.root)], stdout=subprocess.DEVNULL)
        path.write_text(json.dumps({"gates": [{"id": "different", "command": [sys.executable, "-c", "pass"]}]}))
        self.assertIn("stale", self.run_review("complete", id_, "--fix-commit", "HEAD", expected=2))
        self.assertEqual(self.run_review("status")["findings"][id_]["disposition"], "open")


if __name__ == "__main__":
    unittest.main()
