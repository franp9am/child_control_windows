"""
Small overlay showing remaining screen time. 
Displays the remaining time information content from a text file.
"""

import ctypes
import math
import sys
import tkinter as tk

# Only used when no path is passed on the command line; must then match
# REMAINING_TIME_FILE_PATH in monitor.py's config.py.
DEFAULT_REMAINING_TIME_FILE = r"C:\Users\Public\remaining_time.txt"
REMAINING_TIME_FILE_PATH = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REMAINING_TIME_FILE

# Display settings -- used by nothing but this widget.
POLL_INTERVAL_MS = 5000
MARGIN_PX = 20
OPACITY = 0.85
FONT_FAMILY = "Segoe UI"
FONT_SIZE = 14
WARNING_SECONDS = 15 * 60  # orange below this
CRITICAL_SECONDS = 5 * 60  # red below this
COLOR_NORMAL = "#2ecc71"
COLOR_WARNING = "#f39c12"
COLOR_CRITICAL = "#e74c3c"


def format_remaining(seconds):
    """Whole hours and minutes, rounded up so anything under a minute still
    reads as "1 minute" rather than "0 minutes"."""
    seconds = max(0, seconds)
    total_minutes = math.ceil(seconds / 60)
    hours, minutes = divmod(total_minutes, 60)

    parts = []
    if hours:
        parts.append(f"{hours} hour" + ("s" if hours != 1 else ""))
    # Skip minutes only for an exact number of hours (e.g. "2 hours").
    if minutes or not hours:
        parts.append(f"{minutes} minute" + ("s" if minutes != 1 else ""))
    return " ".join(parts)


def color_for(seconds):
    if seconds <= CRITICAL_SECONDS:
        return COLOR_CRITICAL
    if seconds <= WARNING_SECONDS:
        return COLOR_WARNING
    return COLOR_NORMAL


# Pin the widget to the very bottom of the window z-order instead of the top,
# so it only shows through on an empty desktop and is naturally covered by
# whatever window the child opens (or maximizes) over it.
_HWND_BOTTOM = 1
_SWP_NOMOVE = 0x0002
_SWP_NOSIZE = 0x0001
_SWP_NOACTIVATE = 0x0010


class RemainingTimeWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", OPACITY)
        self.root.configure(bg="black")

        self.label = tk.Label(
            self.root,
            text="",
            font=(FONT_FAMILY, FONT_SIZE, "bold"),
            fg=COLOR_NORMAL,
            bg="black",
            padx=12,
            pady=6,
        )
        self.label.pack()

        # overrideredirect windows get no OS close button
        self.root.bind_all("<Alt-F4>", lambda e: self.root.destroy())

        self.root.update_idletasks()
        self._send_to_bottom()
        self.update_label()

    def _position_top_right(self):
        width = self.root.winfo_reqwidth()
        screen_width = self.root.winfo_screenwidth()
        x = screen_width - width - MARGIN_PX
        y = MARGIN_PX
        self.root.geometry(f"+{x}+{y}")

    def _send_to_bottom(self):
        hwnd = self.root.winfo_id()
        ctypes.windll.user32.SetWindowPos(
            hwnd,
            _HWND_BOTTOM,
            0,
            0,
            0,
            0,
            _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOACTIVATE,
        )

    def compute_remaining(self):
        try:
            with open(REMAINING_TIME_FILE_PATH, "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except Exception:
            return None

    def update_label(self):
        remaining = self.compute_remaining()
        if remaining is None:
            text = "Time: --"
            color = COLOR_NORMAL
        elif remaining <= 0:
            text = "Time's up"
            color = COLOR_CRITICAL
        else:
            text = f"{format_remaining(remaining)} remaining"
            color = color_for(remaining)

        self.label.config(text=text, fg=color)
        self._position_top_right()
        self._send_to_bottom()
        self.root.after(POLL_INTERVAL_MS, self.update_label)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    RemainingTimeWidget().run()
