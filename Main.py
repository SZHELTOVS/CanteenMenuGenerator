import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from UI.MainWindow import MainWindow
import tkinter as tk

if __name__ == "__main__":
    app = MainWindow()