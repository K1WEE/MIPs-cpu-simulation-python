import unittest

from isa import ProgramError, cmdDict, load_program

# Machine code worked out by hand from the MIPS32 field layout, not from isa.py
GOLDEN = {
    "ADD $8 $9 $10": 0x012A4020, "ADDU $8 $9 $10": 0x012A4021,
    "SUB $8 $9 $10": 0x012A4022, "SUBU $8 $9 $10": 0x012A4023,
    "AND $8 $9 $10": 0x012A4024, "OR $8 $9 $10": 0x012A4025,
    "XOR $8 $9 $10": 0x012A4026, "NOR $8 $9 $10": 0x012A4027,
    "SLT $8 $9 $10": 0x012A402A, "SLTU $8 $9 $10": 0x012A402B,
    "SLL $8 $9 4": 0x00094100, "SRL $8 $9 4": 0x00094102, "SRA $8 $9 4": 0x00094103,
    "SLLV $8 $9 $10": 0x01494004, "SRLV $8 $9 $10": 0x01494006, "SRAV $8 $9 $10": 0x01494007,
    "JR $31": 0x03E00008, "JALR $31 $9": 0x0120F809,
    "MULT $9 $10": 0x012A0018, "MULTU $9 $10": 0x012A0019,
    "DIV $9 $10": 0x012A001A, "DIVU $9 $10": 0x012A001B,
    "MFHI $8": 0x00004010, "MFLO $8": 0x00004012, "MTHI $9": 0x01200011, "MTLO $9": 0x01200013,
    "MOVZ $8 $9 $10": 0x012A400A, "MOVN $8 $9 $10": 0x012A400B,
    "BREAK": 0x0000000D, "NOP": 0x00000000,
    "TGE $9 $10": 0x012A0030, "TGEU $9 $10": 0x012A0031, "TLT $9 $10": 0x012A0032,
    "TLTU $9 $10": 0x012A0033, "TEQ $9 $10": 0x012A0034, "TNE $9 $10": 0x012A0036,
    "ADDI $8 $9 5": 0x21280005, "ADDI $8 $9 -1": 0x2128FFFF,
    "ADDIU $8 $9 5": 0x25280005, "SLTI $8 $9 5": 0x29280005,
    "SLTIU $8 $9 5": 0x2D280005, "ANDI $8 $9 5": 0x31280005,
    "ORI $8 $9 5": 0x35280005, "XORI $8 $9 5": 0x39280005,
    "LUI $8 0x1234": 0x3C081234,
    "LB $8 4($9)": 0x81280004, "LH $8 4($9)": 0x85280004, "LWL $8 4($9)": 0x89280004,
    "LW $8 4($9)": 0x8D280004, "LBU $8 4($9)": 0x91280004, "LHU $8 4($9)": 0x95280004,
    "LWR $8 4($9)": 0x99280004, "SB $8 4($9)": 0xA1280004, "SH $8 4($9)": 0xA5280004,
    "SWL $8 4($9)": 0xA9280004, "SW $8 4($9)": 0xAD280004, "SWR $8 4($9)": 0xB9280004,
    "LL $8 4($9)": 0xC1280004, "SC $8 4($9)": 0xE1280004,
    "TEQI $9 5": 0x052C0005, "TGEI $9 5": 0x05280005, "TGEIU $9 5": 0x05290005,
    "TLTI $9 5": 0x052A0005, "TLTIU $9 5": 0x052B0005, "TNEI $9 5": 0x052E0005,
    "MUL $8 $9 $10": 0x712A4002, "MADD $9 $10": 0x712A0000, "MADDU $9 $10": 0x712A0001,
    "MSUB $9 $10": 0x712A0004, "MSUBU $9 $10": 0x712A0005,
    "CLZ $8 $9": 0x71284020, "CLO $8 $9": 0x71284021,
    # Offset 1 means the branch skips one instruction
    "BEQ $9 $10 1": 0x112A0001, "BNE $9 $10 1": 0x152A0001,
    "BLEZ $9 1": 0x19200001, "BGTZ $9 1": 0x1D200001,
    "BLTZ $9 1": 0x05200001, "BGEZ $9 1": 0x05210001,
    "BLTZAL $9 1": 0x05300001, "BGEZAL $9 1": 0x05310001,
    "J 0x2000": 0x08000800, "JAL 0x2000": 0x0C000800,
}


def words(source):
    instructions, _ = load_program(source.splitlines())
    return [None if i.hexcmd is None else int(i.hexcmd, 16) for i in instructions]


class Hexcode(unittest.TestCase):
    def test_every_instruction_is_covered(self):
        self.assertEqual(set(cmdDict) - {s.split()[0] for s in GOLDEN}, set())

    def test_golden(self):
        for source, expected in GOLDEN.items():
            with self.subTest(source):
                self.assertEqual(words(source), [expected])

    def test_v7_sample_file(self):
        with open("examples/instructions.txt") as f:
            instructions, _ = load_program(f.read().splitlines())
        self.assertEqual(instructions[0].address, 0x2000)
        self.assertEqual(instructions[0].hexcmd, "3c09ffff")
        self.assertEqual(instructions[7].hexcmd, "0800080c")  # J 0x2030
        self.assertEqual(instructions[-1].opcode, "HALT")
        self.assertIsNone(instructions[-1].hexcmd)


class Syntax(unittest.TestCase):
    def test_commas_names_and_case_are_optional(self):
        same = words("ADD $8 $9 $10")
        for source in ["add $8, $9, $10", "add $t0,$t1,$t2", "Add $T0 $9, $t2"]:
            with self.subTest(source):
                self.assertEqual(words(source), same)

    def test_numbers(self):
        self.assertEqual(words("ORI $8 $0 0x10"), words("ORI $8 $0 16"))
        self.assertEqual(words("ORI $8 $0 0b10000"), words("ORI $8 $0 16"))

    def test_org_and_addresses(self):
        instructions, labels = load_program(["NOP", ".ORG 0x100", "A: NOP", "B:", "NOP"])
        self.assertEqual([i.address for i in instructions], [0, 0x100, 0x104])
        self.assertEqual(labels, {"A": 0x100, "B": 0x104})

    def test_comments_and_blank_lines(self):
        instructions, _ = load_program(["# only a comment", "", "NOP # after"])
        self.assertEqual(len(instructions), 1)

    def test_labels(self):
        self.assertEqual(words("BEQ $9 $10 L\nNOP\nL: NOP")[0], 0x112A0001)
        self.assertEqual(words("L: NOP\nBEQ $0 $0 L")[1], 0x1000FFFE)
        self.assertEqual(words(".ORG 0x2000\nNOP\nL: J L")[1], 0x08000801)

    def test_any_16_bit_pattern_like_v7(self):
        self.assertEqual(words("ADDI $2 $3 0xffff"), words("ADDI $2 $3 -1"))
        self.assertEqual(words("ORI $8 $9 -1"), words("ORI $8 $9 0xffff"))

    def test_jalr_one_operand(self):
        self.assertEqual(words("JALR $9"), [0x0120F809])


class Errors(unittest.TestCase):
    def assert_error(self, source, line, fragment):
        with self.assertRaises(ProgramError) as ctx:
            load_program(source.splitlines())
        match = [m for n, m in ctx.exception.errors if n == line]
        self.assertTrue(match, ctx.exception.errors)
        self.assertIn(fragment, match[0])

    def test_messages_carry_line_numbers(self):
        self.assert_error("NOP\nFOO $8", 2, "Unknown opcode")
        self.assert_error("ADD $8 $9", 1, "needs 3 operand")
        self.assert_error("ADD $8 $9 $99", 1, "Unknown register")
        self.assert_error("ADD $8 $9 10", 1, "Expected a register")
        self.assert_error("NOP\n\nJ NOWHERE", 3, "Unknown label")
        self.assert_error("L: NOP\nL: NOP", 2, "already defined")
        self.assert_error("SLL $8 $9 32", 1, "0-31")
        self.assert_error("ADDI $8 $9 70000", 1, "does not fit")
        self.assert_error("ORI $8 $9 -40000", 1, "does not fit")
        self.assert_error("LW $8 $9", 1, "offset($reg)")
        self.assert_error("J 0x2002", 1, "multiple of 4")
        self.assert_error(".ORG 0x2001", 1, "multiple of 4")
        self.assert_error("HALT $1", 1, "no operands")
        self.assert_error("ADDI $8 $9 zz", 1, "Bad number")

    def test_all_bad_lines_are_reported(self):
        with self.assertRaises(ProgramError) as ctx:
            load_program(["FOO", "NOP", "BAR"])
        self.assertEqual([n for n, _ in ctx.exception.errors], [1, 3])


if __name__ == "__main__":
    unittest.main()
