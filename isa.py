# isa.py
# Handles instruction parsing and decoding, in the same steps as V7:
#   decode()  split label, opcode and operands
#   decode2() prepare value of operands (registers, immediates, labels)
#   decode3() convert instruction to hexcode (8 hex digits, for display and memory)

import re
from dataclasses import dataclass

REG_NAMES = [
    "zero", "at", "v0", "v1", "a0", "a1", "a2", "a3",
    "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
    "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7",
    "t8", "t9", "k0", "k1", "gp", "sp", "fp", "ra",
]
REG_NUMBERS = {name: i for i, name in enumerate(REG_NAMES)}
REG_NUMBERS["s8"] = 30

SPECIAL, REGIMM, SPECIAL2 = 0x00, 0x01, 0x1C


@dataclass(frozen=True)
class Spec:
    name: str
    opcode: int
    operands: tuple      # syntax order, e.g. ("rd", "rs", "rt")
    funct: int = 0       # SPECIAL / SPECIAL2 only
    rt_code: int = 0     # REGIMM only
    imm_kind: str = "s"  # "s" signed 16 bit, "u" unsigned 16 bit, "lui" either


def _build():
    t = []

    def special(name, funct, ops):
        t.append(Spec(name, SPECIAL, tuple(ops.split()), funct=funct))

    def special2(name, funct, ops):
        t.append(Spec(name, SPECIAL2, tuple(ops.split()), funct=funct))

    def regimm(name, code, ops):
        t.append(Spec(name, REGIMM, tuple(ops.split()), rt_code=code))

    def op(name, opcode, ops, kind="s"):
        t.append(Spec(name, opcode, tuple(ops.split()), imm_kind=kind))

    for name, f in [("SLL", 0x00), ("SRL", 0x02), ("SRA", 0x03)]:
        special(name, f, "rd rt sa")
    for name, f in [("SLLV", 0x04), ("SRLV", 0x06), ("SRAV", 0x07)]:
        special(name, f, "rd rt rs")
    special("JR", 0x08, "rs")
    special("JALR", 0x09, "rd rs")
    special("MOVZ", 0x0A, "rd rs rt")
    special("MOVN", 0x0B, "rd rs rt")
    special("BREAK", 0x0D, "")
    special("MFHI", 0x10, "rd")
    special("MTHI", 0x11, "rs")
    special("MFLO", 0x12, "rd")
    special("MTLO", 0x13, "rs")
    for name, f in [("MULT", 0x18), ("MULTU", 0x19), ("DIV", 0x1A), ("DIVU", 0x1B)]:
        special(name, f, "rs rt")
    for name, f in [("ADD", 0x20), ("ADDU", 0x21), ("SUB", 0x22), ("SUBU", 0x23),
                    ("AND", 0x24), ("OR", 0x25), ("XOR", 0x26), ("NOR", 0x27),
                    ("SLT", 0x2A), ("SLTU", 0x2B)]:
        special(name, f, "rd rs rt")
    for name, f in [("TGE", 0x30), ("TGEU", 0x31), ("TLT", 0x32), ("TLTU", 0x33),
                    ("TEQ", 0x34), ("TNE", 0x36)]:
        special(name, f, "rs rt")

    for name, c in [("BLTZ", 0x00), ("BGEZ", 0x01), ("BLTZAL", 0x10), ("BGEZAL", 0x11)]:
        regimm(name, c, "rs label")
    for name, c in [("TGEI", 0x08), ("TGEIU", 0x09), ("TLTI", 0x0A), ("TLTIU", 0x0B),
                    ("TEQI", 0x0C), ("TNEI", 0x0E)]:
        regimm(name, c, "rs imm")

    op("J", 0x02, "target")
    op("JAL", 0x03, "target")
    op("BEQ", 0x04, "rs rt label")
    op("BNE", 0x05, "rs rt label")
    op("BLEZ", 0x06, "rs label")
    op("BGTZ", 0x07, "rs label")
    for name, o in [("ADDI", 0x08), ("ADDIU", 0x09), ("SLTI", 0x0A), ("SLTIU", 0x0B)]:
        op(name, o, "rt rs imm")
    for name, o in [("ANDI", 0x0C), ("ORI", 0x0D), ("XORI", 0x0E)]:
        op(name, o, "rt rs imm", "u")
    op("LUI", 0x0F, "rt imm", "lui")
    for name, o in [("LB", 0x20), ("LH", 0x21), ("LWL", 0x22), ("LW", 0x23), ("LBU", 0x24),
                    ("LHU", 0x25), ("LWR", 0x26), ("SB", 0x28), ("SH", 0x29), ("SWL", 0x2A),
                    ("SW", 0x2B), ("SWR", 0x2E), ("LL", 0x30), ("SC", 0x38)]:
        op(name, o, "rt mem")

    for name, f in [("MADD", 0x00), ("MADDU", 0x01), ("MSUB", 0x04), ("MSUBU", 0x05)]:
        special2(name, f, "rs rt")
    special2("MUL", 0x02, "rd rs rt")
    special2("CLZ", 0x20, "rd rs")
    special2("CLO", 0x21, "rd rs")
    return t


cmdDict = {s.name: s for s in _build()}
_BY_FUNCT = {(s.opcode, s.funct): s for s in cmdDict.values() if s.opcode in (SPECIAL, SPECIAL2)}
_BY_RT = {s.rt_code: s for s in cmdDict.values() if s.opcode == REGIMM}
_BY_OPCODE = {s.opcode: s for s in cmdDict.values() if s.opcode not in (SPECIAL, REGIMM, SPECIAL2)}


def encode(name, rs=0, rt=0, rd=0, sa=0, imm=0, target=0):
    """Pack fields into a 32 bit word. imm is taken as raw 16 bits, target as raw 26 bits."""
    s = cmdDict[name]
    if s.opcode in (SPECIAL, SPECIAL2):
        if name in ("CLZ", "CLO"):
            rt = rd  # MIPS32 requires the rt field to equal rd
        return s.opcode << 26 | rs << 21 | rt << 16 | rd << 11 | sa << 6 | s.funct
    if s.opcode == REGIMM:
        return s.opcode << 26 | rs << 21 | s.rt_code << 16 | (imm & 0xFFFF)
    if "target" in s.operands:
        return s.opcode << 26 | (target & 0x3FFFFFF)
    return s.opcode << 26 | rs << 21 | rt << 16 | (imm & 0xFFFF)


@dataclass(frozen=True)
class Decoded:
    spec: Spec
    rs: int
    rt: int
    rd: int
    sa: int
    uimm: int
    simm: int
    target: int


def decode_word(word):
    """Split a 32 bit word into fields. Returns None if it is not a known instruction."""
    opcode = word >> 26
    if opcode in (SPECIAL, SPECIAL2):
        spec = _BY_FUNCT.get((opcode, word & 0x3F))
    elif opcode == REGIMM:
        spec = _BY_RT.get((word >> 16) & 0x1F)
    else:
        spec = _BY_OPCODE.get(opcode)
    if spec is None:
        return None
    uimm = word & 0xFFFF
    simm = uimm - 0x10000 if uimm & 0x8000 else uimm
    return Decoded(spec, (word >> 21) & 0x1F, (word >> 16) & 0x1F, (word >> 11) & 0x1F,
                   (word >> 6) & 0x1F, uimm, simm, word & 0x3FFFFFF)


class ProgramError(Exception):
    """errors is a list of (line_number, message)."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("\n".join(f"line {line}: {msg}" for line, msg in errors))


class LineError(Exception):
    pass


def imm2int(imm):
    """
    convert immediate in dec, hex (0x) or binary (0b) string to int
    """
    try:
        return int(imm, 0)
    except ValueError:
        raise LineError(f"Bad number {imm!r}") from None


def reg2int(reg):
    """convert $9 or $t1 to 9"""
    if not reg.startswith("$"):
        raise LineError(f"Expected a register, got {reg!r}")
    name = reg[1:].lower()
    if name.isdigit() and int(name) < 32:
        return int(name)
    if name in REG_NUMBERS:
        return REG_NUMBERS[name]
    raise LineError(f"Unknown register {reg}")


LABEL_RE = re.compile(r"^([A-Za-z_][\w.]*):")
NAME_RE = re.compile(r"^[A-Za-z_][\w.]*$")
MEM_RE = re.compile(r"^([-+]?\w*)\((\$\w+)\)$")


class Instruction:
    def __init__(self, raw_line, line_no=0):
        """
        raw_line a single line from the instruction file
        Example: "ADD $1 $2 $3" or "LOOP: BEQ $4 $0 DONE  # comment"
        """
        self.raw = raw_line.strip()
        self.line = line_no
        self.labels = []
        self.opcode = None
        self.operands = []
        self.address = None
        self.fields = {}
        self.hexcmd = None
        self.decoded = None
        self.decode()

    def decode(self):
        """
        Split the instruction into labels, opcode and operands
        """
        text = self.raw.split("#", 1)[0].strip()
        while True:
            m = LABEL_RE.match(text)
            if not m:
                break
            self.labels.append(m.group(1))
            text = text[m.end():].strip()
        if not text:
            return
        parts = [p for p in re.split(r"[\s,]+", text) if p]
        self.opcode = parts[0].upper()
        self.operands = parts[1:]
        if self.opcode not in cmdDict and self.opcode not in ("HALT", "NOP", ".ORG"):
            raise LineError(f"Unknown opcode {parts[0]!r}")

    def decode2(self, labels):
        """
        Prepare value of operands. labels maps label name to address
        """
        if self.opcode in ("HALT", "NOP"):
            self._expect(0)
            return
        spec = cmdDict[self.opcode]
        ops = self.operands
        if self.opcode == "JALR" and len(ops) == 1:
            ops = ["$31"] + ops  # JALR $rs means JALR $31 $rs
        self._expect(len(spec.operands), ops)
        f = self.fields
        for wanted, text in zip(spec.operands, ops):
            if wanted in ("rd", "rs", "rt"):
                f[wanted] = reg2int(text)
            elif wanted == "sa":
                f["sa"] = imm2int(text)
                if not 0 <= f["sa"] <= 31:
                    raise LineError("Shift amount must be 0-31")
            elif wanted == "imm":
                f["imm"] = self._imm16(spec, imm2int(text))
            elif wanted == "mem":
                m = MEM_RE.match(text)
                if not m:
                    raise LineError(f"Expected offset($reg), got {text!r}")
                f["rs"] = reg2int(m.group(2))
                f["imm"] = self._imm16(spec, imm2int(m.group(1) or "0"))
            elif wanted == "label":
                if NAME_RE.match(text):
                    offset = (self._label(labels, text) - (self.address + 4)) >> 2
                else:
                    offset = imm2int(text)  # V7 style: number of instructions to skip
                if not -0x8000 <= offset <= 0x7FFF:
                    raise LineError("Branch target is too far")
                f["imm"] = offset
            elif wanted == "target":
                target = self._label(labels, text) if NAME_RE.match(text) else imm2int(text)
                if target & 3:
                    raise LineError(f"Jump address 0x{target:x} is not a multiple of 4")
                if (target ^ (self.address + 4)) & 0xF0000000:
                    raise LineError(f"Jump address 0x{target:x} is outside the current 256 MB region")
                f["target"] = target >> 2

    def decode3(self):
        """
        Assemble instruction to machine code (8 digit of hex in string)
        """
        if self.opcode == "HALT":
            return  # not a MIPS instruction, so it has no machine code (same as V7)
        word = 0 if self.opcode == "NOP" else encode(self.opcode, **self.fields)
        self.hexcmd = f"{word:08x}"
        self.decoded = decode_word(word)

    def _expect(self, count, ops=None):
        ops = self.operands if ops is None else ops
        if len(ops) != count:
            if count == 0:
                raise LineError(f"{self.opcode} takes no operands")
            usage = " ".join(cmdDict[self.opcode].operands)
            raise LineError(f"{self.opcode} needs {count} operand(s): {self.opcode} {usage}")

    @staticmethod
    def _imm16(spec, value):
        # Any 16 bit pattern is accepted, as in V7: 0xffff in ADDI means -1, -1 in ORI means 0xffff
        if not -0x8000 <= value <= 0xFFFF:
            raise LineError(f"Immediate {value} does not fit in 16 bits (-32768 to 0xffff)")
        return value

    @staticmethod
    def _label(labels, name):
        if name not in labels:
            raise LineError(f"Unknown label {name!r}")
        return labels[name]


def load_program(lines):
    """
    Turn the lines of a program into Instruction objects with addresses.
    Returns (instructions, labels). Raises ProgramError listing every bad line.
    """
    errors, parsed, labels = [], [], {}
    address = 0
    pending = []
    for line_no, raw in enumerate(lines, 1):
        try:
            instr = Instruction(raw, line_no)
        except LineError as e:
            errors.append((line_no, str(e)))
            continue
        pending += [(name, line_no) for name in instr.labels]
        if instr.opcode is None:
            continue
        if instr.opcode == ".ORG":
            try:
                if len(instr.operands) != 1:
                    raise LineError(".ORG needs one address")
                address = imm2int(instr.operands[0])
                if address & 3 or not 0 <= address <= 0xFFFFFFFC:
                    raise LineError(".ORG address must be a multiple of 4")
            except LineError as e:
                errors.append((line_no, str(e)))
            continue
        for name, label_line in pending:
            if name in labels:
                errors.append((label_line, f"Label {name!r} is already defined"))
            labels[name] = address
        pending = []
        instr.address = address
        address += 4
        parsed.append(instr)
    for name, label_line in pending:
        labels.setdefault(name, address)

    for instr in parsed:
        try:
            instr.decode2(labels)
            instr.decode3()
        except LineError as e:
            errors.append((instr.line, str(e)))
    if errors:
        raise ProgramError(sorted(set(errors)))
    return parsed, labels
