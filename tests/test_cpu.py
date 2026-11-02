import unittest

from cpu import CPU, SimulationError


def run(source):
    cpu = CPU(source.splitlines())
    cpu.run(max_steps=100000)
    return cpu


def result(source):
    """Value of $8 after running, as unsigned 32 bit."""
    return run(source).registers[8]


def setreg(reg, value):
    value &= 0xFFFFFFFF
    return f"LUI ${reg} {value >> 16}\nORI ${reg} ${reg} {value & 0xFFFF}\n"


def loads(a, b=0):
    """Put a in $9 and b in $10."""
    return setreg(9, a) + setreg(10, b)


class V7File(unittest.TestCase):
    def test_sample_runs_to_halt(self):
        with open("examples/instructions.txt") as f:
            cpu = run(f.read())
        self.assertEqual(cpu.halted_by, "HALT")
        self.assertEqual(cpu.registers[9], 0)
        self.assertEqual(cpu.registers[10], 0x1F)
        self.assertEqual(cpu.registers[11], 0x20)
        self.assertEqual(cpu.registers[3], 0)  # skipped by BNE
        self.assertEqual(cpu.memory.read_word(0x2000), 0x3C09FFFF)  # code is visible in memory

    def test_halt_stops_before_later_lines(self):
        cpu = run("ADDI $8 $0 1\nHALT\nADDI $8 $0 2")
        self.assertEqual((cpu.registers[8], cpu.halted_by), (1, "HALT"))

    def test_running_past_last_line_stops(self):
        cpu = run("ADDI $8 $0 1")
        self.assertEqual((cpu.running, cpu.halted_by), (False, "end"))


class Alu(unittest.TestCase):
    def test_table(self):
        for source, expected in [
            (loads(5, 7) + "ADD $8 $9 $10", 12),
            (loads(-5, 2) + "ADD $8 $9 $10", 0xFFFFFFFD),
            (loads(0xFFFFFFFF, 1) + "ADDU $8 $9 $10", 0),
            (loads(5, 7) + "SUB $8 $9 $10", 0xFFFFFFFE),
            (loads(5, 7) + "SUBU $8 $9 $10", 0xFFFFFFFE),
            (loads(0xF0F0, 0xFF00) + "AND $8 $9 $10", 0xF000),
            (loads(0xF0F0, 0xFF00) + "OR $8 $9 $10", 0xFFF0),
            (loads(0xF0F0, 0xFF00) + "XOR $8 $9 $10", 0x0FF0),
            (loads(0, 0) + "NOR $8 $9 $10", 0xFFFFFFFF),
            (loads(-1, 1) + "SLT $8 $9 $10", 1),
            (loads(-1, 1) + "SLTU $8 $9 $10", 0),
            (loads(1, -1) + "SLTU $8 $9 $10", 1),
            (loads(-1) + "SLTI $8 $9 0", 1),
            (loads(1) + "SLTIU $8 $9 -1", 1),  # immediate sign extends to 0xffffffff
            (loads(0xFFFFFFFE) + "SLTIU $8 $9 -1", 1),
            (loads(0xFFFFFFFF) + "SLTIU $8 $9 -1", 0),
            (loads(0x8000) + "ANDI $8 $9 0xFFFF", 0x8000),  # zero extended
            (loads(0) + "ADDI $8 $9 -1", 0xFFFFFFFF),
            (loads(0xFFFFFFFF) + "ADDIU $8 $9 2", 1),
            ("LUI $8 0xFFFF", 0xFFFF0000),
            ("LUI $9 0xffff\nORI $8 $9 0xfffe", 0xFFFFFFFE),
        ]:
            with self.subTest(source):
                self.assertEqual(result(source), expected)

    def test_overflow_stops_with_line(self):
        for source in [loads(0x7FFFFFFF, 1) + "ADD $8 $9 $10",
                       loads(-0x80000000, 1) + "SUB $8 $9 $10",
                       loads(0x7FFFFFFF) + "ADDI $8 $9 1"]:
            with self.subTest(source), self.assertRaises(SimulationError) as ctx:
                run(source)
            self.assertIn("overflow", str(ctx.exception))
            self.assertIn("line 5", str(ctx.exception))

    def test_unsigned_add_does_not_trap(self):
        self.assertEqual(result(loads(0x7FFFFFFF, 1) + "ADDU $8 $9 $10"), 0x80000000)

    def test_zero_register_stays_zero(self):
        cpu = run("ADDI $8 $0 5\nADDI $0 $8 1\nADD $9 $0 $0")
        self.assertEqual((cpu.registers[0], cpu.registers[9]), (0, 0))


class Shift(unittest.TestCase):
    def test_table(self):
        for source, expected in [
            (loads(1) + "SLL $8 $9 31", 0x80000000),
            (loads(0x80000000) + "SRL $8 $9 31", 1),
            (loads(0x80000000) + "SRA $8 $9 31", 0xFFFFFFFF),
            (loads(1, 33) + "SLLV $8 $9 $10", 2),  # only the low 5 bits count
            (loads(0x80000000, 4) + "SRLV $8 $9 $10", 0x08000000),
            (loads(0x80000000, 4) + "SRAV $8 $9 $10", 0xF8000000),
        ]:
            with self.subTest(source):
                self.assertEqual(result(source), expected)


class MulDiv(unittest.TestCase):
    def hilo(self, source):
        cpu = run(source)
        return cpu.hi, cpu.lo

    def test_mult(self):
        self.assertEqual(self.hilo(loads(-2, 3) + "MULT $9 $10"), (0xFFFFFFFF, 0xFFFFFFFA))
        self.assertEqual(self.hilo(loads(-2, 3) + "MULTU $9 $10"), (2, 0xFFFFFFFA))
        self.assertEqual(self.hilo(loads(0x10000, 0x10000) + "MULT $9 $10"), (1, 0))
        self.assertEqual(result(loads(-2, 3) + "MULT $9 $10\nMFLO $8"), 0xFFFFFFFA)

    def test_div_truncates_toward_zero(self):
        self.assertEqual(self.hilo(loads(7, 2) + "DIV $9 $10"), (1, 3))
        self.assertEqual(self.hilo(loads(-7, 2) + "DIV $9 $10"), (0xFFFFFFFF, 0xFFFFFFFD))
        self.assertEqual(self.hilo(loads(7, -2) + "DIV $9 $10"), (1, 0xFFFFFFFD))
        self.assertEqual(self.hilo(loads(-7, -2) + "DIV $9 $10"), (0xFFFFFFFF, 3))
        self.assertEqual(self.hilo(loads(-0x80000000, -1) + "DIV $9 $10"), (0, 0x80000000))
        self.assertEqual(self.hilo(loads(0xFFFFFFFF, 2) + "DIVU $9 $10"), (1, 0x7FFFFFFF))

    def test_divide_by_zero_keeps_running(self):
        self.assertEqual(result(loads(7, 0) + "DIV $9 $10\nADDI $8 $0 9"), 9)

    def test_hi_lo_moves(self):
        cpu = run(loads(5, 6) + "MTHI $9\nMTLO $10\nMFHI $11\nMFLO $16")
        self.assertEqual((cpu.registers[11], cpu.registers[16]), (5, 6))

    def test_conditional_moves(self):
        self.assertEqual(result(loads(5, 1) + "MOVN $8 $9 $10"), 5)
        self.assertEqual(result(loads(5, 1) + "MOVZ $8 $9 $10"), 0)
        self.assertEqual(result(loads(5, 0) + "MOVZ $8 $9 $10"), 5)


class Control(unittest.TestCase):
    def taken(self, setup, branch):
        return result(f"{setup}{branch} L\nADDI $8 $0 1\nJ E\nL: ADDI $8 $0 2\nE: NOP") == 2

    def test_branches(self):
        for setup, branch, expected in [
            (loads(1, 1), "BEQ $9 $10", True), (loads(1, 2), "BEQ $9 $10", False),
            (loads(1, 2), "BNE $9 $10", True), (loads(1, 1), "BNE $9 $10", False),
            (loads(0), "BLEZ $9", True), (loads(-1), "BLEZ $9", True), (loads(1), "BLEZ $9", False),
            (loads(1), "BGTZ $9", True), (loads(0), "BGTZ $9", False), (loads(-1), "BGTZ $9", False),
        ]:
            with self.subTest(f"{setup} {branch}"):
                self.assertEqual(self.taken(setup, branch), expected)

    def test_numeric_offset_like_v7(self):
        self.assertEqual(result("BEQ $0 $0 1\nADDI $8 $0 1\nADDI $9 $0 2"), 0)

    def test_jump_to_numeric_address_like_v7(self):
        cpu = run(".ORG 0x2000\nJ 0x2008\nADDI $8 $0 1\nADDI $9 $0 2")
        self.assertEqual((cpu.registers[8], cpu.registers[9]), (0, 2))

    def test_no_delay_slot(self):
        self.assertEqual(result("J L\nADDI $8 $0 1\nL: NOP"), 0)

    def test_backward_loop(self):
        cpu = run("ADDI $9 $0 5\nL: ADDI $8 $8 2\nADDI $9 $9 -1\nBNE $9 $0 L")
        self.assertEqual(cpu.registers[8], 10)

    def test_jal_jr(self):
        cpu = run(".ORG 0x2000\nJAL F\nADDI $9 $0 7\nHALT\nF: ADDI $8 $0 3\nJR $31")
        self.assertEqual((cpu.registers[8], cpu.registers[9], cpu.registers[31]), (3, 7, 0x2004))

    def test_jalr_when_rd_equals_rs(self):
        cpu = run(".ORG 0x2000\nADDI $9 $0 0x2008\nJALR $9 $9\nNOP")
        self.assertEqual(cpu.registers[9], 0x2008)

    def test_bad_pc(self):
        for source in ["ADDI $9 $0 0x100\nJR $9", "ADDI $9 $0 2\nJR $9"]:
            with self.subTest(source), self.assertRaises(SimulationError) as ctx:
                run(source)
            self.assertIn("does not point at an instruction", str(ctx.exception))

    def test_traps(self):
        self.assertEqual(result(loads(1, 2) + "TEQ $9 $10\nADDI $8 $0 9"), 9)
        for source in [
            loads(1, 1) + "TEQ $9 $10", loads(1, 2) + "TNE $9 $10",
            loads(2, 1) + "TGE $9 $10", loads(-1, 1) + "TGEU $9 $10",
            loads(-1, 1) + "TLT $9 $10", loads(1, -1) + "TLTU $9 $10",
            "BREAK",
        ]:
            with self.subTest(source), self.assertRaises(SimulationError):
                run(source)


class LoadStore(unittest.TestCase):
    SETUP = setreg(8, 0x8180FF7F) + "ADDI $9 $0 0x100\nSW $8 0($9)\n" + setreg(8, 0x11223344) + "SW $8 4($9)\n"

    def test_loads(self):
        for source, expected in [
            ("LW $8 0($9)", 0x8180FF7F),
            ("LB $8 0($9)", 0xFFFFFF81),  # big-endian: lowest address holds the high byte
            ("LBU $8 0($9)", 0x81),
            ("LB $8 3($9)", 0x7F),
            ("LH $8 0($9)", 0xFFFF8180),
            ("LHU $8 0($9)", 0x8180),
            ("LH $8 2($9)", 0xFFFFFF7F),
            ("LW $8 4($9)", 0x11223344),
            ("ADDI $9 $9 8\nLW $8 -4($9)", 0x11223344),
        ]:
            with self.subTest(source):
                self.assertEqual(result(self.SETUP + source), expected)

    def test_stores(self):
        cpu = run("ADDI $9 $0 0x100\n" + setreg(8, 0x11223344) + "SW $8 0($9)\n"
                  "ADDI $8 $0 0xAB\nSB $8 1($9)\nADDI $8 $0 0x7DEF\nSH $8 2($9)")
        self.assertEqual(cpu.memory.read_word(0x100), 0x11AB7DEF)

    def test_unaligned_word_helpers(self):
        # Big-endian: bytes at 0x101..0x104 are 22 33 44 55
        setup = ("ADDI $9 $0 0x100\n" + setreg(8, 0x11223344) + "SW $8 0($9)\n"
                 + setreg(8, 0x55667788) + "SW $8 4($9)\n")
        self.assertEqual(result(setup + "ADDI $8 $0 0\nLWL $8 1($9)\nLWR $8 4($9)"), 0x22334455)
        cpu = run(setup + setreg(8, 0xAABBCCDD) + "SWL $8 1($9)\nSWR $8 4($9)")
        self.assertEqual(cpu.memory.read_word(0x100), 0x11AABBCC)
        self.assertEqual(cpu.memory.read_word(0x104), 0xDD667788)

    def test_ll_sc(self):
        setup = "ADDI $9 $0 0x100\nADDI $8 $0 5\nSW $8 0($9)\n"
        cpu = run(setup + "LL $8 0($9)\nADDI $10 $0 9\nSC $10 0($9)")
        self.assertEqual((cpu.registers[8], cpu.registers[10], cpu.memory.read_word(0x100)), (5, 1, 9))
        cpu = run(setup + "ADDI $10 $0 9\nSC $10 0($9)")
        self.assertEqual((cpu.registers[10], cpu.memory.read_word(0x100)), (0, 5))

    def test_unaligned_access_works_like_v7(self):
        cpu = run("ADDI $9 $0 0x101\n" + setreg(8, 0x11223344) + "SW $8 0($9)\nLW $10 0($9)\nLH $11 1($9)")
        self.assertEqual(cpu.registers[10], 0x11223344)
        self.assertEqual(cpu.registers[11], 0x2233)
        self.assertEqual([cpu.memory.peek(a) for a in range(0x100, 0x106)], [0, 0x11, 0x22, 0x33, 0x44, 0])

    def test_teacher_v71_program(self):
        with open("tests/teacher_v71.txt") as f:
            cpu = run(f.read())
        self.assertEqual(cpu.halted_by, "HALT")
        self.assertEqual(cpu.registers[0], 0)
        self.assertEqual(cpu.registers[2], 5)          # 6 + 0xffff (-1)
        self.assertEqual(cpu.registers[3], 6)          # ADDI $3 $0 99 is skipped
        self.assertEqual(cpu.registers[9], 0)          # last set by SLTIU $9 $11 1
        self.assertEqual((cpu.registers[10], cpu.registers[11]), (31, 32))
        self.assertEqual(cpu.registers[12], 0)         # LW 1($0) reads memory that was never written

    def test_reset_restores_state(self):
        cpu = run("ADDI $8 $0 0x100\nSW $8 0($8)")
        cpu.reset()
        self.assertEqual((cpu.registers[8], cpu.memory.read_word(0x100), cpu.PC, cpu.running), (0, 0, 0, True))


if __name__ == "__main__":
    unittest.main()
