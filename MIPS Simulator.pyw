# MIPS Simulator.pyw
# Double-click launcher for Windows. Same as: python main.py --gui
# The .pyw ending makes Windows run it with pythonw, so no console window opens.

import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

try:
    from gui.app import launch
    launch()
except Exception:
    # pythonw has no console, so show the error in a window instead
    import tkinter
    from tkinter import messagebox
    root = tkinter.Tk()
    root.withdraw()
    messagebox.showerror("MIPS Simulator could not start", traceback.format_exc())
    root.destroy()
