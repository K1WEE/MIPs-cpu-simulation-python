import math
import re
import unittest

from cpu import CPU

INT_MAX = 2**31 - 1


def source(name):
    with open(f"examples/{name}") as f:
        return f.read()


def set_input(text, n, k):
    """Replace the n and k lines. LUI + ORI lets the tests use values beyond 16 bits."""
    def load(reg, value):
        value &= 0xFFFFFFFF
        return f"LUI ${reg} {value >> 16}\n        ORI ${reg} ${reg} {value & 0xFFFF}"
    text = re.sub(r"ADDI \$4 \$0 -?\d+", load(4, n), text, count=1)
    return re.sub(r"ADDI \$5 \$0 -?\d+", load(5, k), text, count=1)


def ncr(text, n, k):
    cpu = CPU(set_input(text, n, k).splitlines())
    cpu.run()
    assert cpu.halted_by == "HALT", cpu.halted_by
    return cpu


def signed(value):
    return value - 2**32 if value >= 2**31 else value


class Recursive(unittest.TestCase):
    def test_example_as_written(self):
        cpu = CPU(source("ncr_recursive.txt").splitlines())
        cpu.run()
        self.assertEqual(cpu.registers[2], math.comb(6, 2))

    def test_all_pairs_up_to_15(self):
        text = source("ncr_recursive.txt")
        for n in range(16):
            for k in range(n + 1):
                self.assertEqual(ncr(text, n, k).registers[2], math.comb(n, k), (n, k))

    def test_invalid_inputs_give_zero(self):
        text = source("ncr_recursive.txt")
        for n, k in [(3, 5), (3, -1), (-1, 2), (-2, -3)]:
            self.assertEqual(ncr(text, n, k).registers[2], 0, (n, k))

    def test_stack_is_restored(self):
        cpu = ncr(source("ncr_recursive.txt"), 10, 5)
        self.assertEqual(cpu.registers[29], 0x7000)


class Iterative(unittest.TestCase):
    def test_example_as_written(self):
        cpu = CPU(source("ncr_iterative.txt").splitlines())
        cpu.run()
        self.assertEqual(cpu.registers[2], math.comb(10, 4))

    def test_every_pair_up_to_40(self):
        text = source("ncr_iterative.txt")
        for n in range(41):
            for k in range(n + 1):
                value = math.comb(n, k)
                expected = value if value <= INT_MAX else -1
                self.assertEqual(signed(ncr(text, n, k).registers[2]), expected, (n, k))

    def test_edges_of_32_bits(self):
        text = source("ncr_iterative.txt")
        self.assertEqual(signed(ncr(text, 33, 16).registers[2]), 1166803110)
        self.assertEqual(signed(ncr(text, 34, 17).registers[2]), -1)
        self.assertEqual(signed(ncr(text, 65536, 2).registers[2]), math.comb(65536, 2))
        self.assertEqual(signed(ncr(text, 65537, 2).registers[2]), -1)

    def test_invalid_inputs_give_zero(self):
        text = source("ncr_iterative.txt")
        for n, k in [(3, 5), (3, -1), (-1, 2), (-2, -3)]:
            self.assertEqual(ncr(text, n, k).registers[2], 0, (n, k))


if __name__ == "__main__":
    unittest.main()
