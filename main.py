# main.py
# Entry point for the CPU simulator
#   python3 main.py                          run instructions.txt and show every step (same as V7)
#   python3 main.py file.txt                 run another file the same way
#   python3 main.py -q file.txt              run and show only the final state
#   python3 main.py --print v0 file.txt      run and print only the chosen registers (for Autolab)
#   python3 main.py --gui                    open the window
#
# Exit codes: 0 finished (HALT or past the last line), 1 bad program or command line,
#             2 runtime error, 3 step limit reached

import argparse
import os
import sys

import cpu as cpu_module
from cpu import CPU, ProgramError, SimulationError, s32
from isa import Instruction, LineError, imm2int, reg2int

EXIT_OK, EXIT_BAD_INPUT, EXIT_RUNTIME, EXIT_STEP_LIMIT = 0, 1, 2, 3
DEFAULT_FILE = "instructions.txt"
DEFAULT_MAX_STEPS = 10_000_000
SPECIAL_REGS = ("pc", "hi", "lo")


def load_instructions(filename):
    """
    Load instructions from a text file. Each line is one instruction.
    """
    with open(filename, encoding="utf-8") as file:
        return file.read().splitlines()


def parse_registers(text):
    """
    Turn "v0,$3,10,pc" into register numbers, or "pc"/"hi"/"lo".
    Raises LineError for a name that is not a register.
    """
    keys = []
    for part in text.split(","):
        name = part.strip().lower()
        if not name:
            continue
        if name.lstrip("$") in SPECIAL_REGS:
            keys.append(name.lstrip("$"))
        else:
            keys.append(reg2int(name if name.startswith("$") else "$" + name))
    if not keys:
        raise LineError("No register given")
    return keys


def register_lines(cpu, keys, as_hex):
    lines = []
    for key in keys:
        if key in SPECIAL_REGS:
            label, value = key, {"pc": cpu.PC, "hi": cpu.hi, "lo": cpu.lo}[key]
        else:
            label, value = f"${key}", cpu.registers[key]
        lines.append(f"{label} = {f'0x{value:08x}' if as_hex else s32(value)}")
    return lines


def print_listing(cpu, lines):
    """
    Display address, hexcode and raw instruction of every line before running (same as V7),
    including .ORG lines. Returns the .ORG lines that come before the first instruction.
    """
    by_line = {instr.line: instr for instr in cpu.instructions}
    first_line = cpu.instructions[0].line if cpu.instructions else len(lines) + 1
    leading_orgs = []
    for line_no, raw in enumerate(lines, 1):
        instr = by_line.get(line_no)
        if instr is None:
            parsed = Instruction(raw, line_no)
            if parsed.opcode != ".ORG":
                continue  # blank, comment or label only
            address = imm2int(parsed.operands[0])
            if line_no < first_line:
                leading_orgs.append(parsed)
            print(f"{address:08x} None {parsed.raw}", end="\t")
        else:
            print(f"{instr.address:08x} {instr.hexcmd} {instr.raw}", end="\t")
        print()
    return leading_orgs


def default_file():
    """instructions.txt in the current folder, or else next to main.py (e.g. when started from IDLE)."""
    if os.path.exists(DEFAULT_FILE):
        return DEFAULT_FILE
    beside = os.path.join(os.path.dirname(os.path.abspath(__file__)), DEFAULT_FILE)
    return beside if os.path.exists(beside) else DEFAULT_FILE


def run_file(args):
    filename = args.file or default_file()
    keys = None
    if args.print:
        try:
            keys = parse_registers(args.print)
        except LineError as e:
            print(f"Bad --print value: {e}", file=sys.stderr)
            return EXIT_BAD_INPUT
    try:
        lines = load_instructions(filename)
        cpu = CPU(lines)
    except OSError as e:
        print(f"Cannot open {filename}: {e.strerror}", file=sys.stderr)
        return EXIT_BAD_INPUT
    except ProgramError as e:
        print(e, file=sys.stderr)
        return EXIT_BAD_INPUT

    if args.hex:
        cpu_module.DISP_FORMAT = "HEX"
    trace = keys is None and not args.quiet
    if trace:
        pc = 0
        for org in print_listing(cpu, lines):
            print(f"Executed: {pc:08X} {org.raw}")  # V7 runs .ORG like an instruction
            pc = imm2int(org.operands[0])

    try:
        finished = cpu.run(max_steps=args.max_steps, trace=trace)
    except SimulationError as e:
        print(f"Runtime error at {e}", file=sys.stderr)
        return EXIT_RUNTIME
    if not finished:
        print(f"Stopped: reached the limit of {args.max_steps} instructions "
              f"(PC 0x{cpu.PC:08x}). Is there an endless loop?", file=sys.stderr)
        return EXIT_STEP_LIMIT

    if keys is not None:
        print("\n".join(register_lines(cpu, keys, args.hex)))
    elif args.quiet:
        print(f"Stopped by {cpu.halted_by} after {cpu.steps} instructions")
        print("Last STATE")
        cpu.debug()
    return EXIT_OK


def main():
    parser = argparse.ArgumentParser(description="MIPS32 CPU simulator")
    parser.add_argument("file", nargs="?", help=f"program file to run (default {DEFAULT_FILE})")
    parser.add_argument("--gui", action="store_true", help="open the window")
    parser.add_argument("-q", "--quiet", action="store_true", help="show only the final state")
    parser.add_argument("--print", metavar="REGS",
                        help="print only these registers when the program ends, e.g. v0 or 2,3,pc")
    parser.add_argument("--hex", action="store_true", help="show register values in hex")
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS, metavar="N",
                        help=f"stop after N instructions (default {DEFAULT_MAX_STEPS:,})")
    args = parser.parse_args()
    if args.gui:
        from gui.app import launch
        launch()
        return EXIT_OK
    return run_file(args)


# Only run main() if this file is executed directly (not imported as a module)
if __name__ == "__main__":
    sys.exit(main())
