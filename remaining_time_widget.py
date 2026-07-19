"""
Small always-on-top overlay showing remaining screen time.

Run this in the CHILD's own login session (e.g. via a shortcut in their
Startup folder), not under the system account that runs monitor.py.

It only reads the remaining-time file monitor.py publishes to
C:\\Users\\Public\\ (REMAINING_TIME_FILE_PATH in monitor.py) and never
writes to it, so the child's account only needs read access to that one
file rather than to monitor.py's (hidden) folder or its data files.
"""

import tkinter as tk

# Must match REMAINING_TIME_FILE_PATH in monitor.py.
REMAINING_TIME_FILE_PATH = r"C:\Users\Public\eli_remaining_time.txt"

POLL_INTERVAL_MS = 5000
MARGIN_PX = 20

GREEN = "#2ecc71"
ORANGE = "#f39c12"
RED = "#e74c3c"


def format_remaining(seconds):
    seconds = max(0, seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def color_for(seconds):
    if seconds <= 5 * 60:
        return RED
    if seconds <= 15 * 60:
        return ORANGE
    return GREEN


class RemainingTimeWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.85)
        self.root.configure(bg="black")

        self.label = tk.Label(
            self.root,
            text="",
            font=("Segoe UI", 14, "bold"),
            fg=GREEN,
            bg="black",
            padx=12,
            pady=6,
        )
        self.label.pack()

        # overrideredirect windows get no OS close button, so wire Alt+F4
        # explicitly to let the child close it.
        self.root.bind_all("<Alt-F4>", lambda e: self.root.destroy())

        self.update_label()

    def _position_top_right(self):
        width = self.root.winfo_reqwidth()
        screen_width = self.root.winfo_screenwidth()
        x = screen_width - width - MARGIN_PX
        y = MARGIN_PX
        self.root.geometry(f"+{x}+{y}")

    def compute_remaining(self):
        try:
            with open(REMAINING_TIME_FILE_PATH, "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except Exception:
            return None

    def update_label(self):
        remaining = self.compute_remaining()
        if remaining is None:
            text = "Time: --:--"
            color = GREEN
        elif remaining <= 0:
            text = "Time's up"
            color = RED
        else:
            text = f"Time left: {format_remaining(remaining)}"
            color = color_for(remaining)

        self.label.config(text=text, fg=color)
        self._position_top_right()
        self.root.after(POLL_INTERVAL_MS, self.update_label)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    RemainingTimeWidget().run()
