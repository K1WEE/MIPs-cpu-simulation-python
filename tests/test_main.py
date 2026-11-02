import os
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def run_main(*args, program=None):
    """Run main.py like Autolab would. program is source text written to a temporary file."""
    args = list(args)
    path = None
    if program is not None:
        handle, path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(handle, "w") as f:
            f.write(program)
        args.append(path)
    try:
        return subprocess.run([sys.executable, "main.py", *args], cwd=ROOT,
                              capture_output=True, text=True, timeout=60)
    finally:
        if path:
            os.remove(path)


class PrintRegisters(unittest.TestCase):
    def test_ncr_prints_only_the_answer(self):
        r = run_main("--print", "v0", "examples/ncr_recursive.txt")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "$2 = 15\n", ""))

    def test_v7_file_in_hex(self):
        r = run_main("--print", "10,11", "--hex", "examples/instructions.txt")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "$10 = 0x0000001f\n$11 = 0x00000020\n")

    def test_register_spellings_agree(self):
        for name in ["2", "$2", "v0", "$v0", "V0"]:
            with self.subTest(name):
                self.assertEqual(run_main("--print", name, "examples/ncr_recursive.txt").stdout, "$2 = 15\n")

    def test_special_registers(self):
        r = run_main("--print", "pc,hi,lo", "--hex",
                     program=".ORG 0x100\nADDI $8 $0 7\nADDI $9 $0 3\nDIV $8 $9\nHALT")
        self.assertEqual(r.stdout, "pc = 0x0000010c\nhi = 0x00000001\nlo = 0x00000002\n")

    def test_negative_values_are_signed_unless_hex(self):
        program = "ADDI $8 $0 -5"
        self.assertEqual(run_main("--print", "8", program=program).stdout, "$8 = -5\n")
        self.assertEqual(run_main("--print", "8", "--hex", program=program).stdout, "$8 = 0xfffffffb\n")

    def test_unknown_register(self):
        r = run_main("--print", "v9", "examples/ncr_recursive.txt")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertIn("Unknown register", r.stderr)


class ExitCodes(unittest.TestCase):
    def test_syntax_error(self):
        r = run_main("--print", "2", program="NOP\nFOO $8\n")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertIn("line 2", r.stderr)

    def test_missing_file(self):
        r = run_main("--print", "2", "no_such_file.txt")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertIn("Cannot open", r.stderr)

    def test_runtime_error(self):
        r = run_main("--print", "2", program="LUI $8 0x7fff\nORI $8 $8 0xffff\nADDI $8 $8 1\nHALT")
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertIn("line 3", r.stderr)
        self.assertIn("overflow", r.stderr)

    def test_endless_loop_hits_step_limit(self):
        started = time.time()
        r = run_main("--print", "2", "--max-steps", "1000", program="L: J L")
        self.assertEqual((r.returncode, r.stdout), (3, ""))
        self.assertIn("limit of 1000", r.stderr)
        self.assertLess(time.time() - started, 10)

    def test_step_limit_counts_instructions_exactly(self):
        program = "ADDI $8 $0 1\nADDI $8 $8 1\nADDI $8 $8 1\nHALT"
        self.assertEqual(run_main("--print", "8", "--max-steps", "3", program=program).returncode, 0)
        self.assertEqual(run_main("--print", "8", "--max-steps", "2", program=program).returncode, 3)


REGISTER_ROWS_AFTER_ADDI_0 = """\
Registers:
 0- 4          1          0          0          0          0
 5- 9          0          0          0          0          0
10-14          0          0          0          0          0
15-19          0          0          0          0          0
20-24          0          0          0          0          0
25-29          0          0          0          0          0
30-34          0          0
--------------------------------------------------------------------------------
Memory:
    2000: 20 00 00 01 20 03 00 06 20 62 ff ff 3c 09 ff ff 20 0b 00 20
    2014: 29 69 ff ff 2d 69 ff ff 2d 69 00 01 21 6a ff ff 08 00 08 0c
    2028: 20 15 00 06 ae ab 00 01 8e ac 00 01 11 75 00 01 15 75 00 01
    203c: 20 03 00 63 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    2050: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
--------------------------------------------------------------------------------
****************Warning: register 0 must alwasys be zero
Executed: 00002004 ADDI $3 $0 6
"""


class TraceLikeV7(unittest.TestCase):
    """The default output must look the same as V7 (teacher's screenshot of V7.1 in IDLE)."""

    def setUp(self):
        self.out = run_main("tests/teacher_v71.txt").stdout

    def test_listing(self):
        lines = self.out.splitlines()
        self.assertEqual(lines[0], "00002000 None .ORG 0x2000\t")
        self.assertEqual(lines[1], "00002000 20000001 ADDI $0 $0 1\t")
        self.assertEqual(lines[3], "00002008 2062ffff ADDI $2 $3 0xffff\t")
        self.assertEqual(lines[17], "00002040 None HALT\t")
        self.assertEqual(lines[18], "Executed: 00000000 .ORG 0x2000")
        self.assertEqual(lines[19], "Executed: 00002000 ADDI $0 $0 1")

    def test_first_step_block(self):
        # memory rows end with a space, as in V7
        self.assertIn("    2000: 20 00 00 01 20 03 00 06 20 62 ff ff 3c 09 ff ff 20 0b 00 20 \n", self.out)
        strip = lambda text: "\n".join(line.rstrip() for line in text.splitlines())
        self.assertIn("Executed: 00002000 ADDI $0 $0 1\n" + strip(REGISTER_ROWS_AFTER_ADDI_0), strip(self.out))

    def test_ends_after_halt_block(self):
        self.assertIn("Executed: 00002040 HALT\nRegisters:", self.out)
        self.assertTrue(self.out.endswith("-" * 80 + "\n"))
        self.assertEqual(self.out.count("Executed:"), 15)  # .ORG + 13 instructions (J skips 2) + HALT

    def test_hex_registers(self):
        out = run_main("--hex", "tests/teacher_v71.txt").stdout
        self.assertIn(" 0- 4   00000001   00000000   00000000   00000000   00000000\n", out)


class OldModes(unittest.TestCase):
    def test_no_arguments_runs_instructions_txt(self):
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, "instructions.txt"), "w") as f:
                f.write("ADDI $8 $0 7\nHALT\n")
            r = subprocess.run([sys.executable, os.path.abspath(os.path.join(ROOT, "main.py"))],
                               cwd=folder, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("00000000 20080007 ADDI $8 $0 7\t\n"))
        self.assertIn("Executed: 00000004 HALT", r.stdout)

    def test_trace_of_v7_file(self):
        r = run_main("examples/instructions.txt")
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.startswith("00002000 None .ORG 0x2000\t\n00002000 3c09ffff LUI $9 0xffff\t\n"))
        self.assertIn("Executed: 00002000 LUI $9 0xffff", r.stdout)

    def test_quiet(self):
        r = run_main("-q", "examples/instructions.txt")
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("Executed:", r.stdout)
        self.assertIn("Last STATE", r.stdout)
        self.assertIn("Memory:", r.stdout)


if __name__ == "__main__":
    unittest.main()
