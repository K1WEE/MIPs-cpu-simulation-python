import math
import re
import unittest

from cpu import CPU

FILES = ["factorial_mult.txt", "factorial_nomul.txt"]


def source(name):
    with open(f"examples/{name}") as f:
        return f.read()


def fact(text, n):
    text = re.sub(r"ADDI \$4 \$0 -?\d+", f"ADDI $4 $0 {n}", text, count=1)
    cpu = CPU(text.splitlines())
    cpu.run(max_steps=1_000_000)
    assert cpu.halted_by == "HALT", cpu.halted_by
    return cpu


def signed(value):
    return value - 2**32 if value >= 2**31 else value


class Factorial(unittest.TestCase):
    def test_example_as_written(self):
        for name in FILES:
            with self.subTest(name):
                cpu = CPU(source(name).splitlines())
                cpu.run()
                self.assertEqual(cpu.registers[2], 120)  # 5!

    def test_zero_to_twelve(self):
        for name in FILES:
            text = source(name)
            for n in range(13):
                with self.subTest(name, n=n):
                    self.assertEqual(fact(text, n).registers[2], math.factorial(n))

    def test_too_large_gives_minus_one(self):
        for name in FILES:
            text = source(name)
            for n in range(13, 35):
                with self.subTest(name, n=n):
                    self.assertEqual(signed(fact(text, n).registers[2]), -1)

    def test_negative_gives_zero(self):
        for name in FILES:
            text = source(name)
            for n in (-1, -5):
                with self.subTest(name, n=n):
                    self.assertEqual(fact(text, n).registers[2], 0)

    def test_stack_is_restored(self):
        cpu = fact(source("factorial_nomul.txt"), 10)
        self.assertEqual(cpu.registers[29], 0x7000)

    def test_no_multiply_or_divide_instruction(self):
        cpu = CPU(source("factorial_nomul.txt").splitlines())
        used = {instr.opcode for instr in cpu.instructions}
        self.assertFalse(used & {"MULT", "MULTU", "DIV", "DIVU", "MFHI", "MFLO"}, used)
        cpu = CPU(source("factorial_mult.txt").splitlines())
        self.assertIn("MULT", {instr.opcode for instr in cpu.instructions})


class MultiplySubroutine(unittest.TestCase):
    """Call MULTIPLY on its own with many inputs."""

    def multiply(self, a, b):
        text = source("factorial_nomul.txt")
        main = (f".ORG 0x2000\nLUI $4 {a >> 16}\nORI $4 $4 {a & 0xFFFF}\n"
                f"LUI $5 {b >> 16}\nORI $5 $5 {b & 0xFFFF}\nJAL MULTIPLY\nHALT\n")
        body = text[text.index("\nMULTIPLY:") + 1:]  # the label line, not the comment above it
        cpu = CPU((main + body).splitlines())
        cpu.run(max_steps=100_000)
        return cpu.registers[2], cpu.registers[3]

    def test_products(self):
        for a, b in [(0, 0), (0, 7), (7, 0), (1, 1), (6, 7), (255, 255), (12345, 6789),
                     (46340, 46340), (2**30, 1), (1, 2**31 - 1), (65535, 32768)]:
            with self.subTest(a=a, b=b):
                product = a * b
                result, too_large = self.multiply(a, b)
                if product < 2**31:
                    self.assertEqual((result, too_large), (product, 0))
                else:
                    self.assertEqual(too_large, 1)

    def test_overflow_cases(self):
        for a, b in [(2**31 - 1, 2), (65536, 32768), (46341, 46341), (2**30, 2), (3, 2**30)]:
            with self.subTest(a=a, b=b):
                self.assertEqual(self.multiply(a, b)[1], 1)


if __name__ == "__main__":
    unittest.main()
