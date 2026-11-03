# app.py
# Window for the simulator: editor, program view, registers, memory and messages
# All CPU behaviour lives in cpu.py / isa.py. This file only drives it and shows the result

import os
import sys
import time
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

from cpu import CPU, ProgramError, SimulationError, s32
from isa import REG_NAMES

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "examples")
ICON_FILE = os.path.join(os.path.dirname(__file__), "icon.png")
SPEEDS = {"Max": None, "100 /s": 100, "30 /s": 30, "10 /s": 10, "5 /s": 5, "2 /s": 2, "1 /s": 1}
BATCH = 1000
SLICE_SECONDS = 0.03
GAP_MS = 5
MEMORY_ROWS = 10
ROW_BYTES = 16

CHANGED_BG = "#ffe08a"
CURRENT_BG = "#fff3a3"
ERROR_BG = "#ffc9c9"
INK = "#000000"


def old_tk_warning(patchlevel, platform=sys.platform):
    """Tk before 8.6.13 can miss mouse clicks on newer macOS. Returns a message, or None if fine."""
    if platform != "darwin":
        return None
    try:
        version = tuple(int(part) for part in patchlevel.split(".")[:3])
    except ValueError:
        return None
    if version >= (8, 6, 13):
        return None
    return (f"Warning: this Python uses Tk {patchlevel}, which can miss button clicks on macOS.\n"
            f"Running Python: {sys.executable}\n"
            "Use a Python with Tk 8.6.13 or newer")


class App:
    def __init__(self, root):
        self.root = root
        self.cpu = None
        self.path = None
        self.dirty = False
        self.stale = False
        self.running = False
        self.skip_breakpoint = False
        self.after_id = None
        self.breakpoints = set()
        self.previous_regs = {}
        self.memory_base = 0
        self.previous_memory = {}

        root.title("MIPS32 Simulator")
        root.geometry("1280x800")
        self.icon = tk.PhotoImage(file=ICON_FILE)  # also shown in the Dock / taskbar
        root.iconphoto(True, self.icon)
        self.mono = tkfont.nametofont("TkFixedFont").copy()
        self.mono.configure(size=12)
        ttk.Style(root).configure("Treeview", font=self.mono, rowheight=self.mono.metrics("linespace") + 2)

        self._build_menu()
        self._build_toolbar()
        self._build_body()
        self.status = tk.StringVar(value="Ready")
        ttk.Label(root, textvariable=self.status, anchor="w", padding=(8, 3)).pack(fill="x", side="bottom")
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self._update_buttons()
        self.load_source("")
        self.status.set("Ready. Write a program, or open one from File or Examples")
        warning = old_tk_warning(root.tk.call("info", "patchlevel"))
        if warning:
            self.console_write(warning, "error")
            self.status.set("Old Tk version: buttons may need more than one click")

    # ---- Layout ----
    def _build_menu(self):
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="New", command=self.new_file)
        file_menu.add_command(label="Open...", command=self.open_file)
        file_menu.add_command(label="Save", command=self.save_file)
        file_menu.add_command(label="Save As...", command=self.save_file_as)
        menu.add_cascade(label="File", menu=file_menu)
        example_menu = tk.Menu(menu, tearoff=False)
        for name in sorted(os.listdir(EXAMPLES_DIR)):
            if name.endswith(".txt"):
                example_menu.add_command(label=name, command=lambda n=name: self.open_example(n))
        menu.add_cascade(label="Examples", menu=example_menu)
        self.root.config(menu=menu)

    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=(6, 6))
        bar.pack(fill="x", side="top")
        self.buttons = {}
        for label, command in [("New", self.new_file), ("Open", self.open_file), ("Save", self.save_file),
                               (None, None), ("Load", self.load_program), ("Run", self.run),
                               ("Step", self.step), ("Stop", self.stop), ("Reset", self.reset)]:
            if label is None:
                ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=8)
                continue
            self.buttons[label] = ttk.Button(bar, text=label, command=command, width=9)
            self.buttons[label].pack(side="left", padx=2)
        ttk.Label(bar, text="Speed").pack(side="left", padx=(16, 4))
        self.speed = tk.StringVar(value="Max")
        ttk.Combobox(bar, textvariable=self.speed, values=list(SPEEDS), state="readonly", width=7).pack(side="left")
        self.show_hex = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Hex registers", variable=self.show_hex,
                        command=self._refresh_registers).pack(side="left", padx=16)

    def _build_body(self):
        outer = ttk.PanedWindow(self.root, orient="horizontal")
        outer.pack(fill="both", expand=True, padx=6)
        left = ttk.PanedWindow(outer, orient="vertical")
        outer.add(left, weight=4)
        outer.add(self._build_registers(outer), weight=1)
        self.tabs = ttk.Notebook(left)
        left.add(self.tabs, weight=5)
        left.add(self._build_console(left), weight=1)
        self.tabs.add(self._build_editor(self.tabs), text="Edit")
        self.tabs.add(self._build_execute(self.tabs), text="Execute")

    def _build_editor(self, parent):
        frame = ttk.Frame(parent)
        self.gutter = tk.Canvas(frame, width=44, highlightthickness=0, bg="#eeeeee")
        self.gutter.pack(side="left", fill="y")
        scroll = ttk.Scrollbar(frame, command=self._editor_yview)
        scroll.pack(side="right", fill="y")
        self.editor = tk.Text(frame, font=self.mono, undo=True, wrap="none", tabs=(self.mono.measure("    "),),
                              bg="#ffffff", fg=INK, insertbackground=INK,
                              yscrollcommand=lambda *a: self._on_editor_scroll(scroll, *a))
        self.editor.pack(fill="both", expand=True)
        self.editor.tag_configure("error", background=ERROR_BG, foreground=INK)
        self.editor.bind("<<Modified>>", self._on_modified)
        self.editor.bind("<Configure>", lambda e: self._draw_gutter())
        self.editor.bind("<KeyRelease>", lambda e: self._draw_gutter())
        return frame

    def _editor_yview(self, *args):
        self.editor.yview(*args)
        self._draw_gutter()

    def _on_editor_scroll(self, scroll, *args):
        scroll.set(*args)
        self._draw_gutter()

    def _draw_gutter(self):
        self.gutter.delete("all")
        index = self.editor.index("@0,0")
        while True:
            info = self.editor.dlineinfo(index)
            if info is None:
                break
            self.gutter.create_text(38, info[1], anchor="ne", text=index.split(".")[0], font=self.mono, fill="#666666")
            index = self.editor.index(f"{index}+1line")
            if self.editor.compare(index, ">=", "end"):
                break

    def _build_execute(self, parent):
        frame = ttk.PanedWindow(parent, orient="vertical")
        text_frame = ttk.Frame(frame)
        columns = ("bp", "address", "code", "source")
        self.text_view = ttk.Treeview(text_frame, columns=columns, show="headings", selectmode="none")
        for col, title, width, stretch in [("bp", "Bkpt", 45, False), ("address", "Address", 110, False),
                                           ("code", "Code", 110, False), ("source", "Source", 500, True)]:
            self.text_view.heading(col, text=title, anchor="w")
            self.text_view.column(col, width=width, stretch=stretch, anchor="w")
        self.text_view.tag_configure("current", background=CURRENT_BG, foreground=INK)
        self.text_view.bind("<Button-1>", self._on_text_click)
        scroll = ttk.Scrollbar(text_frame, command=self.text_view.yview)
        self.text_view.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text_view.pack(fill="both", expand=True)
        frame.add(text_frame, weight=3)
        frame.add(self._build_memory(frame), weight=2)
        return frame

    def _build_memory(self, parent):
        frame = ttk.Frame(parent)
        controls = ttk.Frame(frame, padding=(0, 4))
        controls.pack(fill="x")
        ttk.Label(controls, text="Memory").pack(side="left")
        ttk.Button(controls, text="Program", command=lambda: self.goto_memory("program")).pack(side="left", padx=(8, 2))
        ttk.Button(controls, text="$sp", command=lambda: self.goto_memory("sp")).pack(side="left", padx=2)
        self.address_var = tk.StringVar()
        entry = ttk.Entry(controls, textvariable=self.address_var, width=12, font=self.mono)
        entry.pack(side="left", padx=(8, 2))
        entry.bind("<Return>", lambda e: self.goto_memory("entry"))
        ttk.Button(controls, text="Go", command=lambda: self.goto_memory("entry"), width=4).pack(side="left")
        ttk.Button(controls, text="◀", width=3, command=lambda: self.scroll_memory(-1)).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="▶", width=3, command=lambda: self.scroll_memory(1)).pack(side="left")
        columns = ["address"] + [f"b{i}" for i in range(ROW_BYTES)]
        self.memory_view = ttk.Treeview(frame, columns=columns, show="headings", selectmode="none", height=MEMORY_ROWS)
        self.memory_view.heading("address", text="Address", anchor="w")
        self.memory_view.column("address", width=100, stretch=False, anchor="w")
        for i in range(ROW_BYTES):
            self.memory_view.heading(f"b{i}", text=f"{i:x}", anchor="center")
            self.memory_view.column(f"b{i}", width=34, stretch=True, anchor="center")
        self.memory_view.tag_configure("changed", background=CHANGED_BG, foreground=INK)
        for row in range(MEMORY_ROWS):
            self.memory_view.insert("", "end", iid=str(row))
        self.memory_view.pack(fill="both", expand=True)
        return frame

    def _build_registers(self, parent):
        frame = ttk.Frame(parent)
        self.reg_view = ttk.Treeview(frame, columns=("name", "num", "value"), show="headings", selectmode="none", height=35)
        for col, title, width, anchor in [("name", "Name", 65, "w"), ("num", "No.", 40, "e"), ("value", "Value", 125, "e")]:
            self.reg_view.heading(col, text=title, anchor=anchor)
            self.reg_view.column(col, width=width, stretch=col == "value", anchor=anchor)
        self.reg_view.tag_configure("changed", background=CHANGED_BG, foreground=INK)
        for i, name in enumerate(REG_NAMES):
            self.reg_view.insert("", "end", iid=f"r{i}", values=(f"${name}", i, ""))
        for name in ("pc", "hi", "lo"):
            self.reg_view.insert("", "end", iid=name, values=(name, "", ""))
        scroll = ttk.Scrollbar(frame, command=self.reg_view.yview)
        self.reg_view.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.reg_view.pack(fill="both", expand=True)
        return frame

    def _build_console(self, parent):
        frame = ttk.Frame(parent)
        bar = ttk.Frame(frame)
        bar.pack(fill="x", side="bottom", pady=(4, 0))
        ttk.Button(bar, text="Clear messages", command=self.clear_console).pack(side="right")
        self.console = tk.Text(frame, height=7, font=self.mono, state="disabled", wrap="word", bg="#ffffff", fg=INK)
        self.console.tag_configure("error", foreground="#b00020")
        self.console.tag_configure("info", foreground="#555555")
        self.console.pack(fill="both", expand=True)
        return frame

    # ---- Files ----
    def load_source(self, text, path=None):
        self.stop()
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", text)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.path = path
        self.dirty = False
        self.cpu = None
        self.stale = False
        self.tabs.select(0)
        self._clear_program_views()
        self._update_title()
        self._update_buttons()
        self.root.update_idletasks()
        self._draw_gutter()

    def load_example(self, name):
        with open(os.path.join(EXAMPLES_DIR, name), encoding="utf-8") as f:
            self.load_source(f.read())
        self.status.set(f"Opened example {name}. Press Load")

    def _confirm_discard(self):
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel("Unsaved changes", "Save changes first?")
        if answer is None:
            return False
        return self.save_file() if answer else True

    def new_file(self):
        if self._confirm_discard():
            self.load_source("")

    def open_example(self, name):
        if self._confirm_discard():
            self.load_example(name)

    def open_file(self):
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(filetypes=[("Program", "*.txt *.asm *.s"), ("All files", "*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                self.load_source(f.read(), path)
        except (OSError, UnicodeDecodeError) as e:
            messagebox.showerror("Cannot open file", str(e))

    def save_file(self):
        if not self.path:
            return self.save_file_as()
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(self.editor.get("1.0", "end-1c"))
        except OSError as e:
            messagebox.showerror("Cannot save file", str(e))
            return False
        self.dirty = False
        self._update_title()
        self.status.set(f"Saved {self.path}")
        return True

    def save_file_as(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Program", "*.txt *.asm")])
        if not path:
            return False
        self.path = path
        return self.save_file()

    def quit(self):
        if self._confirm_discard():
            self.stop()
            self.root.destroy()

    def _update_title(self):
        name = os.path.basename(self.path) if self.path else "untitled"
        self.root.title(f"{'*' if self.dirty else ''}{name} - MIPS32 Simulator")

    def _on_modified(self, event):
        if not self.editor.edit_modified():
            return
        self.editor.edit_modified(False)
        self.dirty = True
        self.editor.tag_remove("error", "1.0", "end")
        if self.cpu is not None:
            self.stop()
            self.stale = True
            self.status.set("Program changed. Press Load again")
        self._update_title()
        self._update_buttons()
        self._draw_gutter()

    # ---- Messages ----
    def console_write(self, text, tag=None):
        self.console.configure(state="normal")
        self.console.insert("end", text, (tag,) if tag else ())
        self.console.see("end")
        self.console.configure(state="disabled")

    def clear_console(self):
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")

    # ---- Program control ----
    def load_program(self):
        self.stop()
        self.editor.tag_remove("error", "1.0", "end")
        try:
            cpu = CPU(self.editor.get("1.0", "end-1c").splitlines())
        except ProgramError as e:
            self.cpu = None
            self._clear_program_views()
            for line, message in e.errors:
                self.console_write(f"Error on line {line}: {message}\n", "error")
                self.editor.tag_add("error", f"{line}.0", f"{line}.end+1c")
            self.tabs.select(0)
            self.editor.see(f"{e.errors[0][0]}.0")
            self.status.set(f"Load failed: {len(e.errors)} error(s)")
            self._update_buttons()
            return False
        self.cpu = cpu
        self.stale = False
        self.breakpoints.clear()
        self._fill_text_view()
        self.memory_base = self._program_start()
        self.previous_regs = {}
        self.previous_memory = {}
        self.tabs.select(1)
        self.refresh()
        self.status.set(f"Loaded {len(cpu.instructions)} instructions")
        self._update_buttons()
        return True

    def _program_start(self):
        if self.cpu and self.cpu.instructions:
            return self.cpu.instructions[0].address & ~(ROW_BYTES - 1)
        return 0

    def _fill_text_view(self):
        self.text_view.delete(*self.text_view.get_children())
        for instr in self.cpu.instructions:
            self.text_view.insert("", "end", iid=str(instr.address),
                                  values=("", f"0x{instr.address:08x}", instr.hexcmd or "--------",
                                          f"{instr.line}: {instr.raw}"))

    def _clear_program_views(self):
        self.text_view.delete(*self.text_view.get_children())
        self.previous_regs = {}
        self.previous_memory = {}
        self.refresh()

    def _on_text_click(self, event):
        if self.text_view.identify_column(event.x) != "#1":
            return
        iid = self.text_view.identify_row(event.y)
        if iid:
            self.toggle_breakpoint(int(iid))

    def toggle_breakpoint(self, address):
        self.breakpoints.symmetric_difference_update({address})
        self.text_view.set(str(address), "bp", "●" if address in self.breakpoints else "")

    def _ready(self):
        return self.cpu is not None and self.cpu.running and not self.running and not self.stale

    def run(self):
        if not self._ready():
            return
        self.running = True
        self.skip_breakpoint = True
        self.status.set("Running...")
        self._update_buttons()
        self._tick()

    def step(self):
        if not self._ready():
            return
        self.skip_breakpoint = True
        self._advance(1)
        self.refresh()
        self._update_buttons()

    def stop(self):
        was_running = self.running
        self.running = False
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        if was_running:
            self.status.set("Stopped")
            self.refresh()
            self._update_buttons()

    def reset(self):
        if self.cpu is None or self.stale:
            return
        self.stop()
        self.cpu.reset()
        self.previous_regs = {}
        self.previous_memory = {}
        self.refresh()
        self.status.set("Reset. Ready to run")
        self._update_buttons()

    def _tick(self):
        self.after_id = None
        if not self.running:
            return
        rate = SPEEDS[self.speed.get()]
        if rate is None:
            # Work in short slices with a real gap, or Tk never gets to handle clicks
            deadline = time.monotonic() + SLICE_SECONDS
            keep_going = self._advance(BATCH)
            while keep_going and time.monotonic() < deadline:
                keep_going = self._advance(BATCH)
        else:
            keep_going = self._advance(1)
        self.refresh()
        if keep_going:
            self.after_id = self.root.after(GAP_MS if rate is None else max(1, 1000 // rate), self._tick)
        else:
            self.running = False
            self._update_buttons()

    def _advance(self, count):
        """Execute up to count instructions. Returns True if the program can keep going."""
        cpu = self.cpu
        for _ in range(count):
            if cpu.PC in self.breakpoints and not self.skip_breakpoint:
                self.status.set(f"Breakpoint at 0x{cpu.PC:08x}")
                return False
            self.skip_breakpoint = False
            try:
                cpu.step()
            except SimulationError as e:
                self.console_write(f"Runtime error on {e}\n", "error")
                self.status.set("Stopped by a runtime error")
                return False
            if not cpu.running:
                how = "HALT" if cpu.halted_by == "HALT" else "end of program"
                self.console_write(f"-- stopped by {how} after {cpu.steps} instructions, "
                                   f"$2 = {s32(cpu.registers[2])} --\n", "info")
                self.status.set(f"Finished ({how})")
                return False
        if not self.running:
            self.status.set(f"Stepped to 0x{cpu.PC:08x}")
        return True

    # ---- Display ----
    def _fmt(self, value):
        return f"0x{value:08x}" if self.show_hex.get() else str(s32(value))

    def refresh(self):
        self._refresh_registers()
        self._refresh_memory()
        self._refresh_current_line()

    def _refresh_registers(self):
        cpu = self.cpu
        if cpu is None:
            values = {f"r{i}": 0 for i in range(32)} | {"pc": 0, "hi": 0, "lo": 0}
        else:
            values = {f"r{i}": cpu.registers[i] for i in range(32)} | {"pc": cpu.PC, "hi": cpu.hi, "lo": cpu.lo}
        for iid, value in values.items():
            changed = iid != "pc" and iid in self.previous_regs and self.previous_regs[iid] != value
            self.reg_view.set(iid, "value", f"0x{value:08x}" if iid == "pc" else self._fmt(value))
            self.reg_view.item(iid, tags=("changed",) if changed else ())
        self.previous_regs = values

    def goto_memory(self, where):
        if where == "program":
            base = self._program_start()
        elif where == "sp":
            base = self.cpu.registers[29] if self.cpu else 0
        else:
            try:
                base = int(self.address_var.get().strip(), 0)
            except ValueError:
                self.status.set(f"Not an address: {self.address_var.get()!r}")
                return
        self.memory_base = base & ~(ROW_BYTES - 1) & 0xFFFFFFFF
        self.previous_memory = {}
        self._refresh_memory()

    def scroll_memory(self, direction):
        self.memory_base = (self.memory_base + direction * MEMORY_ROWS * ROW_BYTES) & 0xFFFFFFFF
        self.previous_memory = {}
        self._refresh_memory()

    def _refresh_memory(self):
        current = {}
        for row in range(MEMORY_ROWS):
            base = (self.memory_base + row * ROW_BYTES) & 0xFFFFFFFF
            data = [self.cpu.memory.peek(base + i) if self.cpu else 0 for i in range(ROW_BYTES)]
            current[row] = data
            changed = row in self.previous_memory and self.previous_memory[row] != data
            self.memory_view.item(str(row), values=[f"0x{base:08x}"] + [f"{b:02x}" for b in data],
                                  tags=("changed",) if changed else ())
        self.previous_memory = current

    def _refresh_current_line(self):
        for iid in self.text_view.tag_has("current"):
            self.text_view.item(iid, tags=())
        if self.cpu is None or not self.cpu.running:
            return
        iid = str(self.cpu.PC)
        if self.text_view.exists(iid):
            self.text_view.item(iid, tags=("current",))
            self.text_view.see(iid)

    def _update_buttons(self):
        idle = self._ready()
        self._enable("Run", idle)
        self._enable("Step", idle)
        self._enable("Stop", self.running)
        self._enable("Reset", self.cpu is not None and not self.stale)

    def _enable(self, name, on):
        self.buttons[name].state(["!disabled"] if on else ["disabled"])


def launch():
    root = tk.Tk()
    App(root)
    root.mainloop()
