# main.py
# Entry point for the CPU simulator
#   python3 main.py                open the window
#   python3 main.py file.txt       run the file in the terminal, showing registers after every step
#   python3 main.py -q file.txt    run the file and show only the final state

import argparse
import sys

from cpu import CPU, ProgramError, SimulationError


def load_instructions(filename):
    """
    Load instructions from a text file. Each line is one instruction.
    """
    with open(filename, encoding="utf-8") as file:
        return file.read().splitlines()


def run_file(filename, quiet):
    try:
        cpu = CPU(load_instructions(filename))
    except ProgramError as e:
        print(e, file=sys.stderr)
        return 1

    # display address, hexcode and raw instruction before running (same as V7)
    for instr in cpu.instructions:
        print(f"{instr.address:08x} {instr.hexcmd or '--------'} {instr.raw}")
    print()

    try:
        cpu.run(trace=not quiet)
    except SimulationError as e:
        print(f"Runtime error at {e}", file=sys.stderr)
        return 1
    print(f"Stopped by {cpu.halted_by} after {cpu.steps} instructions")
    print("Last STATE")
    cpu.debug()
    if cpu.instructions:
        cpu.memory.dump(cpu.instructions[0].address)
    return 0


def main():
    parser = argparse.ArgumentParser(description="MIPS32 CPU simulator")
    parser.add_argument("file", nargs="?", help="program file to run in the terminal")
    parser.add_argument("-q", "--quiet", action="store_true", help="show only the final state")
    args = parser.parse_args()
    if args.file:
        return run_file(args.file, args.quiet)
    from gui.app import launch
    launch()
    return 0


# Only run main() if this file is executed directly (not imported as a module)
if __name__ == "__main__":
    sys.exit(main())
