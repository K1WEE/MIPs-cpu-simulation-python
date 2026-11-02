#memory.py
#simulates byte addressable main memory for the CPU, words are big-endian (same as V7)

class MemoryError_(Exception):
    pass


class Memory:
    def __init__(self):
        #Dictionary to store memory values
        #Key -> byte address
        #value -> byte stored at that address (0-255)
        self.data = {}

    def _check(self, address, size):
        if address & (size - 1):
            kind = {2: "halfword", 4: "word"}[size]
            raise MemoryError_(f"Address 0x{address:08x} is not aligned to a {kind} boundary")

    def read(self, address, size=1):
        """
        Return the value of size bytes starting at address.
        Bytes that have never been written to read as 0.
        """
        self._check(address, size)
        value = 0
        for i in range(size):
            value = value << 8 | self.data.get((address + i) & 0xFFFFFFFF, 0)
        return value

    def write(self, address, value, size=1):
        """
        Write size bytes of value starting at address.
        """
        self._check(address, size)
        for i in range(size):
            shift = 8 * (size - 1 - i)
            self.data[(address + i) & 0xFFFFFFFF] = (value >> shift) & 0xFF

    def read_byte(self, address): return self.read(address, 1)
    def read_half(self, address): return self.read(address, 2)
    def read_word(self, address): return self.read(address, 4)
    def write_byte(self, address, value): self.write(address, value, 1)
    def write_half(self, address, value): self.write(address, value, 2)
    def write_word(self, address, value): self.write(address, value, 4)

    def peek(self, address):
        """Read one byte without any checks, for the display."""
        return self.data.get(address & 0xFFFFFFFF, 0)

    def dump(self, start=0, width=20, count=100):
        print("Memory:")
        for i in range(start, start + count):
            if (i - start) % width == 0:
                if i != start: print()
                print(f"{i:>8x}: ", end="")
            print(f"{self.peek(i):02x}", end=" ")
        print()


if __name__ == "__main__":
    a = Memory()
    a.write(0x2000, 0x12345678, 4)
    a.dump(0x2000)
