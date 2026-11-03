import os
import plistlib
import subprocess
import sys
import tempfile
import unittest

APP = "MIPS Simulator.app"
LAUNCHER = os.path.join(APP, "Contents", "MacOS", "launcher")


def launcher(*args, **env):
    return subprocess.run(["bash", LAUNCHER, *args], capture_output=True, text=True,
                          env={**os.environ, **env}, timeout=60)


class MacApp(unittest.TestCase):
    def test_info_plist_points_at_launcher(self):
        with open(os.path.join(APP, "Contents", "Info.plist"), "rb") as f:
            info = plistlib.load(f)
        self.assertEqual(info["CFBundlePackageType"], "APPL")
        self.assertEqual(info["CFBundleExecutable"], os.path.basename(LAUNCHER))
        icon = os.path.join(APP, "Contents", "Resources", info["CFBundleIconFile"] + ".icns")
        self.assertTrue(os.path.isfile(icon), icon)

    def test_launcher_is_executable_bash(self):
        self.assertTrue(os.access(LAUNCHER, os.X_OK))
        self.assertEqual(subprocess.run(["bash", "-n", LAUNCHER]).returncode, 0)

    @unittest.skipUnless(sys.platform == "darwin", "macOS only")
    def test_chooses_python_with_tkinter(self):
        result = launcher("--which-python")
        self.assertEqual(result.returncode, 0, result.stderr)
        chosen = result.stdout.strip()
        check = subprocess.run([chosen, "-c", "import tkinter"])
        self.assertEqual(check.returncode, 0, chosen)

    def test_mips_python_overrides_choice(self):
        result = launcher("--which-python", MIPS_PYTHON=sys.executable)
        self.assertEqual(result.stdout.strip(), sys.executable)

    def test_failed_start_reports_error(self):
        with tempfile.TemporaryDirectory() as home:
            result = launcher(MIPS_PYTHON="/usr/bin/false", MIPS_NO_DIALOG="1", HOME=home)
            self.assertEqual(result.returncode, 1)
            self.assertIn("stopped with an error", result.stderr)
            with open(os.path.join(home, "Library", "Logs", "mips-simulator.log")) as f:
                self.assertIn("using /usr/bin/false", f.read())


class WindowsLauncher(unittest.TestCase):
    def test_pyw_compiles(self):
        with open("MIPS Simulator.pyw", encoding="utf-8") as f:
            compile(f.read(), "MIPS Simulator.pyw", "exec")


if __name__ == "__main__":
    unittest.main()
