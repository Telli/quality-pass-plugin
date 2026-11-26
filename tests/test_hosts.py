import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generator = load("build_host_agents", ROOT / "scripts/build-host-agents.py")
installer = load("cross_host_installer", ROOT / "scripts/install.py")
GEMINI_FIELDS = {"kind", "name", "description", "display_name", "tools", "mcp_servers", "model", "temperature", "max_turns", "timeout_mins"}
GEMINI_TOOLS = {"read_file", "read_many_files", "grep_search", "glob", "list_directory", "run_shell_command"}


def frontmatter(text):
    header = text.split("---\n", 2)[1]
    return dict(line.split(": ", 1) for line in header.strip().splitlines())


class HostAgentTests(unittest.TestCase):
    def test_generated_files_are_current(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/build-host-agents.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_claude_agent_pins_model_and_effort(self):
        for path in sorted((ROOT / "agents").glob("qp-*.md")):
            with self.subTest(agent=path.name):
                fields = frontmatter(path.read_text(encoding="utf-8"))
                self.assertIn(fields["model"], {"opus", "sonnet", "haiku", "fable", "inherit"})
                self.assertIn(fields["effort"], {"low", "medium", "high", "xhigh", "max"})

    def test_gemini_agents_use_only_fields_and_tools_gemini_accepts(self):
        files = generator.generate()
        agents = {p: c for p, c in files.items() if p.startswith("gemini/agents/")}
        self.assertEqual(len(agents), len(list((ROOT / "agents").glob("qp-*.md"))))
        for path, content in agents.items():
            with self.subTest(agent=path):
                fields = frontmatter(content)
                self.assertLessEqual(set(fields), GEMINI_FIELDS)
                self.assertRegex(fields["name"], r"^[a-z0-9_-]+$")
                tools = re.fullmatch(r"\[(.*)\]", fields["tools"]).group(1).split(", ")
                self.assertLessEqual(set(tools), GEMINI_TOOLS)
                self.assertNotIn("write_file", tools)
                self.assertNotIn("replace", tools)

    def test_codex_agents_are_valid_toml_with_required_fields(self):
        try:
            import tomllib
        except ImportError:
            self.skipTest("tomllib requires Python 3.11+")
        for path, content in generator.generate().items():
            if not path.endswith(".toml"):
                continue
            with self.subTest(file=path):
                data = tomllib.loads(content)
                if path.startswith("codex/agents/"):
                    self.assertRegex(data["name"], r"^[A-Za-z0-9_]+$")
                    self.assertTrue(data["description"] and data["developer_instructions"].strip())
                    self.assertIn("read-only", data["developer_instructions"])
                else:
                    self.assertIn("{{args}}", data["prompt"])

    def test_quoted_tier_keeps_host_pins(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "qp-x.md"
            path.write_text('---\nname: qp-x\ndescription: d\nmodel: "sonnet"\neffort: \'high\'\n---\nbody\n')
            agent = generator.parse_agent(path)
        self.assertEqual((agent["model"], agent["effort"]), ("sonnet", "high"))

    def test_writer_emits_lf_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            generator.write_files({"a/b.toml": "x = 1\ny = 2\n"}, Path(temp))
            self.assertEqual((Path(temp) / "a/b.toml").read_bytes(), b"x = 1\ny = 2\n")

    def test_null_model_inherits_session_model(self):
        agent = {"name": "qp-x", "description": "d", "model": "opus", "effort": "high", "body": "b\n"}
        models = {"codex": {"opus": None, "effort": {}}, "gemini": {"opus": None}}
        self.assertNotIn("model =", generator.codex_agent(agent, models))
        self.assertNotIn("model_reasoning_effort", generator.codex_agent(agent, models))
        self.assertIn("model: inherit", generator.gemini_agent(agent, models))


class CrossHostInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="quality pass home ")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def install(self, *hosts, expected=0, copy=True):
        args = [a for h in hosts for a in ("--host", h)] + (["--copy"] if copy else [])
        env = dict(os.environ)
        env.pop("CODEX_HOME", None)
        result = subprocess.run([sys.executable, str(ROOT / "scripts/install.py"), "--home", str(self.home), *args],
                                capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_installs_user_wide_for_codex_gemini_and_antigravity(self):
        self.install("codex", "gemini", "antigravity")
        for skills in (self.home / ".agents/skills", self.home / ".gemini/antigravity-cli/skills"):
            self.assertEqual(sorted(p.name for p in skills.iterdir() if not p.name.startswith(".")),
                             sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir()))
        self.assertTrue((self.home / ".codex/agents/qp_bug_hunter.toml").is_file())
        self.assertTrue((self.home / ".gemini/agents/qp-bug-hunter.md").is_file())
        self.assertTrue((self.home / ".gemini/commands/quality-pass/review.toml").is_file())
        self.install("codex", "gemini", "antigravity")

    def test_gemini_gets_standalone_skills_and_codex_links(self):
        self.install("codex", copy=False)
        skill = self.home / ".agents/skills/quality-pass-review"
        if not skill.is_symlink():
            self.skipTest("Symlink privilege unavailable")
        self.install("codex", "gemini", copy=False)
        self.assertFalse(skill.is_symlink())
        self.assertTrue((skill / "references/quality-pass.md").is_file())
        self.assertNotIn("../quality-pass/", (skill / "SKILL.md").read_text(encoding="utf-8"))

    def test_fresh_gemini_install_uses_standalone_copies(self):
        self.install("gemini", copy=False)
        skill = self.home / ".agents/skills/quality-pass-review"
        self.assertFalse(skill.is_symlink())
        self.assertTrue((skill / ".quality-pass-package.json").is_file())
        self.assertNotIn("../quality-pass/", (skill / "SKILL.md").read_text(encoding="utf-8"))

    def test_codex_only_rerun_refreshes_managed_copies(self):
        self.install("codex", "antigravity", copy=False)
        skill = self.home / ".agents/skills/quality-pass-gate"
        self.assertTrue((skill / ".quality-pass-package.json").is_file())
        self.install("codex", copy=False)
        self.assertFalse(skill.is_symlink())

    def test_antigravity_profile_alone_does_not_select_gemini(self):
        (self.home / ".gemini/antigravity-cli").mkdir(parents=True)
        with unittest.mock.patch.object(installer.shutil, "which", return_value=None):
            self.assertEqual(installer.detected(self.home), {"antigravity"})
            (self.home / ".gemini/settings.json").write_text("{}")
            self.assertEqual(installer.detected(self.home), {"antigravity", "gemini"})

    def test_modified_and_unrelated_agent_files_are_preserved(self):
        agents = self.home / ".gemini/agents"
        agents.mkdir(parents=True)
        (agents / "mine.md").write_text("unrelated")
        (agents / "qp-slop-reviewer.md").write_text("someone else's agent")
        self.install("gemini", expected=1)
        self.assertEqual((agents / "qp-slop-reviewer.md").read_text(), "someone else's agent")
        self.assertEqual((agents / "mine.md").read_text(), "unrelated")
        bug = agents / "qp-bug-hunter.md"
        bug.write_text(bug.read_text() + "local tweak\n")
        self.install("gemini", expected=1)
        self.assertTrue(bug.read_text().endswith("local tweak\n"))

    def test_unmodified_installed_file_is_refreshed_and_retired_file_removed(self):
        self.install("codex")
        agents = self.home / ".codex/agents"
        manifest = json.loads((agents / ".quality-pass-installed.json").read_text())
        stale = agents / "qp_retired.toml"
        stale.write_text("old")
        manifest["files"]["qp_retired.toml"] = generator_digest("old")
        target = agents / "qp_bug_hunter.toml"
        target.write_text("older generated version")
        manifest["files"]["qp_bug_hunter.toml"] = generator_digest("older generated version")
        (agents / ".quality-pass-installed.json").write_text(json.dumps(manifest))
        self.install("codex")
        self.assertFalse(stale.exists())
        self.assertIn("developer_instructions", target.read_text())


class ClaudeSourceTests(unittest.TestCase):
    def check(self, listing, source):
        result = unittest.mock.Mock(stdout=json.dumps(listing))
        with unittest.mock.patch.object(installer.subprocess, "run", return_value=result):
            return installer.registered_source_matches("claude", source)

    def test_same_source_duplicate_continues_and_different_source_fails(self):
        github = [{"name": installer.MARKETPLACE, "source": "github", "repo": "Telli/quality-pass-plugin"}]
        self.assertTrue(self.check(github, "telli/quality-pass-plugin"))
        self.assertFalse(self.check(github, str(ROOT)))
        local = [{"name": installer.MARKETPLACE, "source": "directory", "path": str(ROOT)}]
        self.assertTrue(self.check(local, str(ROOT)))
        self.assertFalse(self.check(local, "telli/quality-pass-plugin"))
        self.assertFalse(self.check([], str(ROOT)))

    def test_rerun_on_cli_that_rejects_duplicates_still_updates(self):
        calls = []

        def fake_run(command):
            calls.append(command[1:])
            if command[1:4] == ["plugin", "marketplace", "add"]:
                return 1, f"Marketplace '{installer.MARKETPLACE}' is already installed"
            if command[1:3] == ["plugin", "install"]:
                return 0, "already installed"
            return 0, ""
        with unittest.mock.patch.object(installer.shutil, "which", return_value="claude"), \
                unittest.mock.patch.object(installer, "run", side_effect=fake_run), \
                unittest.mock.patch.object(installer, "registered_source_matches", return_value=True):
            self.assertEqual(installer.install_claude("telli/quality-pass-plugin", True), [])
        self.assertIn(["plugin", "update", installer.PLUGIN, "--scope", "user"], calls)
        with unittest.mock.patch.object(installer.shutil, "which", return_value="claude"), \
                unittest.mock.patch.object(installer, "run", side_effect=fake_run), \
                unittest.mock.patch.object(installer, "registered_source_matches", return_value=False):
            self.assertEqual(len(installer.install_claude("telli/quality-pass-plugin", True)), 1)


class RetiredSymlinkTests(unittest.TestCase):
    def test_user_symlink_to_identical_copy_survives_retirement(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "agents"
            installer.install_files({"qp_old.toml": "x = 1\n"}, target)
            copy = Path(temp) / "mine.toml"
            copy.write_text("x = 1\n")
            (target / "qp_old.toml").unlink()
            try:
                (target / "qp_old.toml").symlink_to(copy)
            except OSError:
                self.skipTest("Symlink privilege unavailable")
            installer.install_files({}, target)
            self.assertTrue((target / "qp_old.toml").is_symlink())
            installer.install_files({"qp_new.toml": "y = 2\n"}, target)
            self.assertTrue((target / "qp_old.toml").is_symlink())


def generator_digest(text):
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


if __name__ == "__main__":
    unittest.main()
