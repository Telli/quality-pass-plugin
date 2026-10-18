import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import skill_packages
spec = importlib.util.spec_from_file_location("installer", ROOT / "scripts/install-codex.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="standalone skills ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def install(self, *args, expected=0):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/install-codex.py"), "--target", str(self.root / "installed"), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_every_archive_is_deterministic_and_works_in_isolation(self):
        for name in sorted(p.name for p in skill_packages.SKILLS.iterdir() if p.is_dir()):
            with self.subTest(skill=name):
                first = skill_packages.write_package(name, self.root / f"{name}.zip")
                second = skill_packages.write_package(name, self.root / f"{name}-second.zip")
                self.assertEqual(first.read_bytes(), second.read_bytes())
                self.assertEqual(skill_packages.validate_archive(first), name)
                with zipfile.ZipFile(first) as archive:
                    self.assertIn(f"{name}/scripts/common.py", archive.namelist())
                    self.assertIn(f"{name}/references/quality-pass.md", archive.namelist())

    def test_selected_skill_has_no_siblings_and_runs(self):
        self.install("--skill", "quality-pass-execute")
        installed = self.root / "installed"
        self.assertEqual([p.name for p in installed.iterdir()], ["quality-pass-execute"])
        skill = installed / "quality-pass-execute"
        self.assertFalse(skill.is_symlink())
        self.assertNotIn("../quality-pass/", (skill / "SKILL.md").read_text())
        subprocess.check_call([sys.executable, str(skill / "scripts/review.py"), "--help"], stdout=subprocess.DEVNULL)
        self.install("--skill", "quality-pass-execute")

    def test_copy_preserves_modified_files_and_unowned_directories(self):
        self.install("--copy")
        skill = self.root / "installed/quality-pass-review"
        (skill / "SKILL.md").write_text("user modifications")
        self.install("--skill", "quality-pass-review", expected=1)
        self.assertEqual((skill / "SKILL.md").read_text(), "user modifications")
        unknown = self.root / "installed/quality-pass-gate"
        (unknown / ".quality-pass-package.json").unlink()
        self.install("--skill", "quality-pass-gate", expected=1)
        self.assertTrue((unknown / "SKILL.md").exists())

    def test_all_links_repeat_without_overwrite(self):
        self.install()
        self.install()
        for name in (p.name for p in skill_packages.SKILLS.iterdir() if p.is_dir()):
            path = self.root / "installed" / name
            if os.name == "nt" and not path.is_symlink():
                self.assertTrue((path / ".quality-pass-package.json").exists())
            else:
                self.assertEqual(path.resolve(), skill_packages.SKILLS / name)

    def test_unrelated_symlink_is_preserved(self):
        target = self.root / "installed"
        target.mkdir()
        unrelated = self.root / "unrelated"
        unrelated.mkdir()
        path = target / "quality-pass-gate"
        try:
            path.symlink_to(unrelated, target_is_directory=True)
        except OSError:
            self.skipTest("Symlink privilege unavailable")
        self.install("--skill", "quality-pass-gate", expected=1)
        self.assertEqual(path.resolve(), unrelated.resolve())

    def test_selected_skill_replaces_own_link_with_standalone_copy(self):
        self.install()
        path = self.root / "installed/quality-pass-gate"
        if not path.is_symlink():
            self.skipTest("Symlink privilege unavailable")
        self.install("--skill", "quality-pass-gate")
        self.assertFalse(path.is_symlink())
        self.assertTrue((path / ".quality-pass-package.json").is_file())
        self.assertTrue((skill_packages.SKILLS / "quality-pass-gate/SKILL.md").is_file())

    def test_unknown_skill_and_missing_argument_fail_cleanly(self):
        self.install("--skill", "../outside", expected=1)
        self.install("--target", expected=2)

    def test_windows_symlink_fallback_copy_refreshes_without_flags(self):
        target = self.root / "fallback"
        target.mkdir()
        with patch.object(installer, "WINDOWS", True), patch.object(Path, "symlink_to", side_effect=OSError("No symlink privilege")):
            installer.install("quality-pass-gate", target, False)
            installer.install("quality-pass-gate", target, False)
        self.assertTrue((target / "quality-pass-gate/.quality-pass-package.json").exists())


if __name__ == "__main__":
    unittest.main()
