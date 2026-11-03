import time
import tkinter as tk
import unittest

from gui.app import App, old_tk_warning


class TkVersion(unittest.TestCase):
    def test_old_tk_on_mac_warns(self):
        message = old_tk_warning("8.6.12", "darwin")
        self.assertIn("Tk 8.6.12", message)
        self.assertIn("8.6.13 or newer", message)
        self.assertIsNotNone(old_tk_warning("8.5.9", "darwin"))

    def test_new_tk_or_other_systems_are_quiet(self):
        self.assertIsNone(old_tk_warning("8.6.13", "darwin"))
        self.assertIsNone(old_tk_warning("8.6.15", "darwin"))
        self.assertIsNone(old_tk_warning("9.0.1", "darwin"))
        self.assertIsNone(old_tk_warning("8.6.12", "win32"))
        self.assertIsNone(old_tk_warning("8.6b1", "darwin"))


class GuiBase(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as e:
            self.skipTest(f"No display: {e}")
        self.app = App(self.root)

    def tearDown(self):
        self.app.dirty = False
        self.app.quit()

    def pump(self, condition, seconds=20):
        """Run the real Tk main loop until condition() is true, checking from a timer like a user would."""
        end = time.time() + seconds

        def check():
            if condition() or time.time() > end:
                self.root.quit()
            else:
                self.root.after(20, check)

        self.root.after(20, check)
        self.root.mainloop()
        self.assertTrue(condition(), "timed out")

    def finish(self):
        self.pump(lambda: not self.app.cpu.running and not self.app.running)

    def console(self):
        return self.app.console.get("1.0", "end-1c")

    def reg(self, iid):
        return self.app.reg_view.set(iid, "value")

    def disabled(self, button):
        return "disabled" in self.app.buttons[button].state()


class Flow(GuiBase):
    def test_all_registers_fit_on_a_laptop_screen(self):
        self.root.geometry("1280x705")
        self.root.update()
        for iid in ("r0", "r31", "pc", "hi", "lo"):
            self.assertTrue(self.app.reg_view.bbox(iid), iid)

    def test_window_has_icon(self):
        self.assertEqual((self.app.icon.width(), self.app.icon.height()), (256, 256))

    def test_starts_with_empty_editor(self):
        self.assertEqual(self.app.editor.get("1.0", "end-1c"), "")
        self.assertEqual(self.app.tabs.index("current"), 0)
        self.assertFalse(self.app.dirty)
        self.assertTrue(self.disabled("Run"))

    def test_run_recursive_ncr(self):
        app = self.app
        app.load_example("ncr_recursive.txt")
        self.assertTrue(app.load_program())
        self.assertEqual(app.tabs.index("current"), 1)
        app.run()
        self.finish()
        self.assertEqual(app.cpu.halted_by, "HALT")
        self.assertEqual(self.reg("r2"), "0x0000000f")  # C(6, 2) = 15
        self.assertIn("stopped by HALT", self.console())
        self.assertIn("$2 = 15", self.console())
        self.assertTrue(self.disabled("Run"))

    def test_v7_file(self):
        app = self.app
        app.load_example("instructions.txt")
        app.load_program()
        self.assertEqual(app.text_view.set("8192", "code"), "3c09ffff")
        self.assertEqual(app.text_view.set("8248", "code"), "--------")  # HALT
        self.assertEqual(app.memory_view.set("0", "b0"), "3c")
        app.run()
        self.finish()
        self.assertEqual((self.reg("r10"), self.reg("r11")), ("0x0000001f", "0x00000020"))

    def test_step_updates_display_and_highlights(self):
        app = self.app
        app.load_source(".ORG 0x100\nADDI $8 $0 5\nADDI $9 $0 6\nADD $10 $8 $9\nHALT")
        app.load_program()
        self.assertEqual(app.text_view.tag_has("current"), ("256",))
        app.step()
        self.assertEqual(self.reg("r8"), "0x00000005")
        self.assertIn("changed", app.reg_view.item("r8", "tags"))
        self.assertEqual(self.reg("pc"), "0x00000104")
        self.assertEqual(app.text_view.tag_has("current"), ("260",))
        app.step()
        self.assertEqual(app.reg_view.item("r8", "tags"), "")
        app.step()
        app.show_hex.set(False)
        app._refresh_registers()
        self.assertEqual(self.reg("r10"), "11")
        app.step()
        self.assertEqual(app.cpu.halted_by, "HALT")
        self.assertTrue(self.disabled("Step"))

    def test_breakpoint_stops_and_resumes(self):
        app = self.app
        app.load_source("ADDI $8 $0 1\nADDI $9 $0 2\nADDI $10 $0 3\nHALT")
        app.load_program()
        app.toggle_breakpoint(4)
        self.assertEqual(app.text_view.set("4", "bp"), "●")
        app.run()
        self.pump(lambda: not app.running)
        self.assertEqual((app.cpu.PC, app.cpu.registers[9]), (4, 0))
        self.assertIn("Breakpoint", app.status.get())
        app.run()
        self.finish()
        self.assertEqual(app.cpu.registers[10], 3)

    def test_stop_interrupts_infinite_loop(self):
        app = self.app
        app.load_source("L: ADDI $8 $8 1\nADDI $8 $0 0\nJ L")
        app.load_program()
        app.run()
        self.pump(lambda: app.cpu.steps > 20000)
        # Queue a real mouse click on Stop behind the running program's events
        stop = app.buttons["Stop"]
        stop.event_generate("<Enter>", when="tail")
        stop.event_generate("<ButtonPress-1>", x=5, y=5, when="tail")
        stop.event_generate("<ButtonRelease-1>", x=5, y=5, when="tail")
        clicked = time.time()
        self.pump(lambda: not app.running, seconds=2)
        self.assertLess(time.time() - clicked, 0.5)
        steps = app.cpu.steps
        self.pump(lambda: time.time() - clicked > 0.7, seconds=2)
        self.assertEqual(app.cpu.steps, steps)
        self.assertTrue(app.cpu.running)

    def test_reset_restores_state(self):
        app = self.app
        app.load_source(".ORG 0x100\nADDI $9 $0 0x200\nADDI $8 $0 9\nSW $8 0($9)\nHALT")
        app.load_program()
        app.run()
        self.finish()
        app.address_var.set("0x200")
        app.goto_memory("entry")
        self.assertEqual(app.memory_view.set("0", "b3"), "09")
        app.reset()
        self.assertEqual(app.memory_view.set("0", "b3"), "00")
        self.assertEqual(self.reg("r8"), "0x00000000")
        self.assertEqual(self.reg("pc"), "0x00000100")

    def test_load_error_marks_line_and_blocks_run(self):
        app = self.app
        app.load_source("NOP\nFOO $8\nNOP")
        self.assertFalse(app.load_program())
        self.assertIn("Error on line 2", self.console())
        self.assertEqual(app.tabs.index("current"), 0)
        self.assertEqual(str(app.editor.tag_ranges("error")[0]), "2.0")
        self.assertTrue(self.disabled("Run"))

    def test_runtime_error_shows_line(self):
        app = self.app
        app.load_source("NOP\nLUI $9 0x7fff\nORI $8 $9 0xffff\nADDI $8 $8 1\nNOP")
        app.load_program()
        app.run()
        self.finish()
        self.assertIn("line 4", self.console())
        self.assertIn("overflow", self.console())

    def test_edit_makes_program_stale(self):
        app = self.app
        app.load_source("NOP")
        app.load_program()
        self.root.update()
        app.editor.insert("end", "\nNOP")
        self.root.update()
        self.assertTrue(app.stale)
        self.assertTrue(self.disabled("Step"))
        app.load_program()
        self.assertFalse(app.stale)
        self.assertEqual(len(app.cpu.instructions), 2)

    def test_stack_view_follows_sp(self):
        app = self.app
        app.load_source("ADDI $29 $0 0x7000\nADDI $29 $29 -16\nADDI $8 $0 7\nSW $8 0($29)\nHALT")
        app.load_program()
        app.run()
        self.finish()
        app.goto_memory("sp")
        self.assertEqual(app.memory_view.set("0", "address"), "0x00006ff0")
        self.assertEqual(app.memory_view.set("0", "b3"), "07")


if __name__ == "__main__":
    unittest.main()
