#cpu.py
#simulates a MIPS32 CPU: fetch the Instruction at PC, execute it, validate, repeat
#PC holds the real byte address. There is no branch delay slot.

from isa import ProgramError, cmdDict, load_program
from memory import Memory, MemoryError_

DISP_FORMAT = "INT"  # INT or HEX form, for debug()

M32 = 0xFFFFFFFF
M64 = 0xFFFFFFFFFFFFFFFF


class SimulationError(Exception):
    pass


def s32(value):
    return value - 0x100000000 if value & 0x80000000 else value


def _checked(result):
    if not -0x80000000 <= result <= 0x7FFFFFFF:
        raise SimulationError("Arithmetic overflow")
    return result & M32


def _sext(value, bits):
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


# ---- ALU ----
def _add(c, d): c.registers[d.rd] = _checked(s32(c.registers[d.rs]) + s32(c.registers[d.rt]))
def _addu(c, d): c.registers[d.rd] = (c.registers[d.rs] + c.registers[d.rt]) & M32
def _sub(c, d): c.registers[d.rd] = _checked(s32(c.registers[d.rs]) - s32(c.registers[d.rt]))
def _subu(c, d): c.registers[d.rd] = (c.registers[d.rs] - c.registers[d.rt]) & M32
def _and(c, d): c.registers[d.rd] = c.registers[d.rs] & c.registers[d.rt]
def _or(c, d): c.registers[d.rd] = c.registers[d.rs] | c.registers[d.rt]
def _xor(c, d): c.registers[d.rd] = c.registers[d.rs] ^ c.registers[d.rt]
def _nor(c, d): c.registers[d.rd] = ~(c.registers[d.rs] | c.registers[d.rt]) & M32
def _slt(c, d): c.registers[d.rd] = int(s32(c.registers[d.rs]) < s32(c.registers[d.rt]))
def _sltu(c, d): c.registers[d.rd] = int(c.registers[d.rs] < c.registers[d.rt])
def _addi(c, d): c.registers[d.rt] = _checked(s32(c.registers[d.rs]) + d.simm)
def _addiu(c, d): c.registers[d.rt] = (c.registers[d.rs] + d.simm) & M32
def _andi(c, d): c.registers[d.rt] = c.registers[d.rs] & d.uimm
def _ori(c, d): c.registers[d.rt] = c.registers[d.rs] | d.uimm
def _xori(c, d): c.registers[d.rt] = c.registers[d.rs] ^ d.uimm
def _lui(c, d): c.registers[d.rt] = d.uimm << 16
def _slti(c, d): c.registers[d.rt] = int(s32(c.registers[d.rs]) < d.simm)
def _sltiu(c, d): c.registers[d.rt] = int(c.registers[d.rs] < (d.simm & M32))


# ---- Shift ----
def _sll(c, d): c.registers[d.rd] = (c.registers[d.rt] << d.sa) & M32
def _srl(c, d): c.registers[d.rd] = c.registers[d.rt] >> d.sa
def _sra(c, d): c.registers[d.rd] = (s32(c.registers[d.rt]) >> d.sa) & M32
def _sllv(c, d): c.registers[d.rd] = (c.registers[d.rt] << (c.registers[d.rs] & 31)) & M32
def _srlv(c, d): c.registers[d.rd] = c.registers[d.rt] >> (c.registers[d.rs] & 31)
def _srav(c, d): c.registers[d.rd] = (s32(c.registers[d.rt]) >> (c.registers[d.rs] & 31)) & M32


# ---- Multiply / divide ----
def _set_hilo(c, value):
    value &= M64
    c.hi, c.lo = value >> 32, value & M32


def _mult(c, d): _set_hilo(c, s32(c.registers[d.rs]) * s32(c.registers[d.rt]))
def _multu(c, d): _set_hilo(c, c.registers[d.rs] * c.registers[d.rt])


def _div(c, d):
    a, b = s32(c.registers[d.rs]), s32(c.registers[d.rt])
    if b == 0:
        return  # HI and LO are undefined, the program keeps running
    q = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        q = -q
    c.lo, c.hi = q & M32, (a - q * b) & M32


def _divu(c, d):
    a, b = c.registers[d.rs], c.registers[d.rt]
    if b:
        c.lo, c.hi = a // b, a % b


def _mfhi(c, d): c.registers[d.rd] = c.hi
def _mflo(c, d): c.registers[d.rd] = c.lo
def _mthi(c, d): c.hi = c.registers[d.rs]
def _mtlo(c, d): c.lo = c.registers[d.rs]


def _movn(c, d):
    if c.registers[d.rt]:
        c.registers[d.rd] = c.registers[d.rs]


def _movz(c, d):
    if not c.registers[d.rt]:
        c.registers[d.rd] = c.registers[d.rs]


# ---- Branch / jump: PC already points at the next instruction ----
def _take(c, d): c.PC = (c.PC + d.simm * 4) & M32


def _beq(c, d):
    if c.registers[d.rs] == c.registers[d.rt]: _take(c, d)


def _bne(c, d):
    if c.registers[d.rs] != c.registers[d.rt]: _take(c, d)


def _blez(c, d):
    if s32(c.registers[d.rs]) <= 0: _take(c, d)


def _bgtz(c, d):
    if s32(c.registers[d.rs]) > 0: _take(c, d)


def _j(c, d): c.PC = (c.PC & 0xF0000000) | (d.target << 2)


def _jal(c, d):
    c.registers[31] = c.PC
    _j(c, d)


def _jr(c, d): c.PC = c.registers[d.rs]


def _jalr(c, d):
    target = c.registers[d.rs]
    c.registers[d.rd] = c.PC
    c.PC = target


# ---- Load / store ----
def _addr(c, d): return (c.registers[d.rs] + d.simm) & M32
def _lb(c, d): c.registers[d.rt] = _sext(c.memory.read_byte(_addr(c, d)), 8) & M32
def _lbu(c, d): c.registers[d.rt] = c.memory.read_byte(_addr(c, d))
def _lh(c, d): c.registers[d.rt] = _sext(c.memory.read_half(_addr(c, d)), 16) & M32
def _lhu(c, d): c.registers[d.rt] = c.memory.read_half(_addr(c, d))
def _lw(c, d): c.registers[d.rt] = c.memory.read_word(_addr(c, d))
def _sb(c, d): c.memory.write_byte(_addr(c, d), c.registers[d.rt])
def _sh(c, d): c.memory.write_half(_addr(c, d), c.registers[d.rt])
def _sw(c, d): c.memory.write_word(_addr(c, d), c.registers[d.rt])


def _unaligned_parts(address):
    """Return the aligned word address and how many bytes from the word's high end (big-endian)."""
    return address & ~3 & M32, address & 3


def _lwl(c, d):
    base, n = _unaligned_parts(_addr(c, d))
    word = c.memory.read_word(base)
    keep = (1 << 8 * n) - 1
    c.registers[d.rt] = ((word << 8 * n) & M32) | (c.registers[d.rt] & keep)


def _lwr(c, d):
    base, n = _unaligned_parts(_addr(c, d))
    word = c.memory.read_word(base)
    shift = 8 * (3 - n)
    c.registers[d.rt] = (word >> shift) | (c.registers[d.rt] & ~(M32 >> shift) & M32)


def _swl(c, d):
    base, n = _unaligned_parts(_addr(c, d))
    word = c.memory.read_word(base)
    shift = 8 * n
    c.memory.write_word(base, (word & ~(M32 >> shift) & M32) | (c.registers[d.rt] >> shift))


def _swr(c, d):
    base, n = _unaligned_parts(_addr(c, d))
    word = c.memory.read_word(base)
    shift = 8 * (3 - n)
    c.memory.write_word(base, ((c.registers[d.rt] << shift) & M32) | (word & ((1 << shift) - 1)))


def _ll(c, d):
    address = _addr(c, d)
    c.registers[d.rt] = c.memory.read_word(address)
    c.ll_address = address


def _sc(c, d):
    address = _addr(c, d)
    if c.ll_address == address:
        c.memory.write_word(address, c.registers[d.rt])
        c.registers[d.rt] = 1
    else:
        c.registers[d.rt] = 0
    c.ll_address = None


# ---- Trap ----
def _trap_if(condition):
    if condition:
        raise SimulationError("Trap")


def _tge(c, d): _trap_if(s32(c.registers[d.rs]) >= s32(c.registers[d.rt]))
def _tgeu(c, d): _trap_if(c.registers[d.rs] >= c.registers[d.rt])
def _tlt(c, d): _trap_if(s32(c.registers[d.rs]) < s32(c.registers[d.rt]))
def _tltu(c, d): _trap_if(c.registers[d.rs] < c.registers[d.rt])
def _teq(c, d): _trap_if(c.registers[d.rs] == c.registers[d.rt])
def _tne(c, d): _trap_if(c.registers[d.rs] != c.registers[d.rt])
def _break(c, d): raise SimulationError("BREAK instruction")


EXECUTE = {name: globals()["_" + name.lower()] for name in cmdDict}


class CPU:
    def __init__(self, instructions):
        """
        instructions: list of instruction strings (lines of the program file)
        Raises ProgramError if any line is wrong.
        """
        self.instructions, self.labels = load_program(instructions)
        self.by_address = {instr.address: instr for instr in self.instructions}
        self.reset()

    def reset(self):
        self.memory = Memory()
        # copy all instruction hexcode to memory, so it can be seen (same as V7)
        for instr in self.instructions:
            if instr.hexcmd is not None:
                self.memory.write(instr.address, int(instr.hexcmd, 16), 4)
        self.registers = [0] * 32
        self.hi = 0
        self.lo = 0
        self.PC = self.instructions[0].address if self.instructions else 0
        self.running = True
        self.trace = False      # print each step like V7
        self.halted_by = None   # "HALT", "end" or the error message
        self.steps = 0
        self.ll_address = None

    @property
    def end_address(self):
        return self.instructions[-1].address + 4 if self.instructions else 0

    def fetch(self):
        """
        Fetch the next instruction using PC. Returns None when the program has ended.
        """
        instr = self.by_address.get(self.PC)
        if instr is None:
            if self.PC == self.end_address:
                return None  # ran past the last line, stop like V7
            raise SimulationError(f"PC 0x{self.PC:08x} does not point at an instruction")
        return instr

    def validate(self):
        """
        Check all registers are valid: $0 is always 0, values stay 32 bit
        """
        if self.registers[0] != 0 and self.trace:
            print("****************Warning: register 0 must alwasys be zero")
        self.registers[0] = 0
        for i in range(32):
            self.registers[i] &= M32

    def step(self):
        """
        Fetch, execute and validate one instruction. Returns the Instruction executed or None.
        """
        if not self.running:
            return None
        pc = self.PC
        try:
            instr = self.fetch()
            if instr is None:
                self.running = False
                self.halted_by = "end"
                return None
            if self.trace:
                print(f"Executed: {pc:08X} {instr.raw}")
            if instr.opcode == "HALT":
                self.running = False
                self.halted_by = "HALT"
                if self.trace:
                    self.debug()
                return instr
            self.PC = (pc + 4) & M32
            self.execute(instr)
        except (SimulationError, MemoryError_) as e:
            self.PC = pc
            self.running = False
            line = self.by_address[pc].line if pc in self.by_address else None
            where = f"line {line} " if line else ""
            self.halted_by = f"{where}(0x{pc:08x}): {e}"
            raise SimulationError(self.halted_by) from None
        if self.trace:
            self.debug()  # before validate, so a wrong $0 is shown first (same as V7)
        self.validate()
        self.steps += 1
        return instr

    def execute(self, instr):
        """
        Execute a single instruction
        """
        if instr.opcode == "NOP":
            return
        EXECUTE[instr.opcode](self, instr.decoded)

    def run(self, max_steps=None, trace=False):
        """
        Main fetch-decode-execute loop. Returns False if max_steps was reached first.
        """
        self.trace = trace
        while self.running:
            if max_steps is not None and self.steps >= max_steps and not self._at_stop():
                return False
            self.step()
        return True

    def _at_stop(self):
        """True if the next step only stops the program (HALT or past the last line), which is not counted."""
        instr = self.by_address.get(self.PC)
        return self.PC == self.end_address if instr is None else instr.opcode == "HALT"

    def debug(self):
        """
        Show all registers
        """
        W = 5
        print("Registers:")
        for i, val in enumerate(self.registers):
            if i % W == 0: print(f"{i:>2}-{i + W - 1:>2}", end="")
            if DISP_FORMAT == "HEX":
                print(f"{val:08x}".rjust(11), end="")
            else:
                print(f"{s32(val):>11}", end="")
            if i % W == W - 1: print()
        print("\n" + "-" * 80)
        self.memory.dump(self.instructions[0].address if self.instructions else 0)  # start from the program
        print("-" * 80)


__all__ = ["CPU", "SimulationError", "ProgramError", "s32"]
