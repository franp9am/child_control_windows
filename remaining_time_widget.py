"""
Small overlay showing remaining screen time.
Displays the remaining time information content from a text file.
"""

import ctypes
import math
import sys
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

# The installer puts this script in the same folder as the file it displays.
DEFAULT_REMAINING_TIME_FILE = Path(__file__).parent / "remaining_time.txt"
REMAINING_TIME_FILE_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_REMAINING_TIME_FILE

# The monitor rewrites the file once per check interval (60 s); well past that
# and it has died or been killed, so the number on screen means nothing.
STALE_AFTER_SECONDS = 150

# Display settings -- used by nothing but this widget.
POLL_INTERVAL_MS = 5000
MARGIN_PX = 20
# Which top corner to sit in, "right" or "left". Right is the real spot; left is
# for trying a copy out next to the one already running.
CORNER = "right"
OPACITY = 0.85
FONT_FAMILY = "Segoe UI"
FONT_SIZE = 14
WARNING_SECONDS = 15 * 60  # orange below this
CRITICAL_SECONDS = 5 * 60  # red below this
COLOR_NORMAL = "#2ecc71"
COLOR_WARNING = "#f39c12"
COLOR_CRITICAL = "#e74c3c"

# Ctrl+Alt+H hides the widget, the same combination brings it back. The keyboard
# state is read directly rather than claiming the combination from Windows, so
# it works whatever app has focus and cannot clash with another program's
# shortcut. The keys still reach that app as well.
HOTKEY_POLL_MS = 100
_VK_CONTROL = 0x11
_VK_ALT = 0x12
_VK_H = 0x48
HOTKEY_KEYS = (_VK_CONTROL, _VK_ALT, _VK_H)
_KEY_IS_DOWN = 0x8000

# Tk can make the window borderless, topmost, translucent and taskbar-free by
# itself. These are the two things it has no attribute for: clicks falling
# through to whatever is underneath (so the box never blocks the close button of
# a maximised window) and never taking focus from the app in use.
_GWL_EXSTYLE = -20
_WS_EX_TRANSPARENT = 0x00000020
_WS_EX_NOACTIVATE = 0x08000000
_GA_ROOT = 2  # winfo_id() names an inner window; this walks up to the real one

_user32 = ctypes.windll.user32
# Spelled out because the defaults would truncate window handles to 32 bits on
# 64-bit Windows.
_user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
_user32.GetAncestor.restype = wintypes.HWND
_user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
_user32.GetWindowLongW.restype = ctypes.c_long
_user32.SetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_long)
_user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
_user32.GetAsyncKeyState.restype = ctypes.c_short


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


def hotkey_is_down():
    """True while every key of the toggle shortcut is held at once."""
    return all(_user32.GetAsyncKeyState(key) & _KEY_IS_DOWN for key in HOTKEY_KEYS)


class RemainingTimeWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", OPACITY)
        self.root.attributes("-topmost", True)
        self.root.attributes("-toolwindow", True)  # no taskbar button, no Alt+Tab entry
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

        self.hidden = False
        self.hotkey_was_down = False

        self.root.update_idletasks()
        self._apply_click_through()

        self.root.after(HOTKEY_POLL_MS, self.check_hotkey)
        self.update_label()

    def _apply_click_through(self):
        hwnd = _user32.GetAncestor(self.root.winfo_id(), _GA_ROOT)
        style = _user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
        _user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, style | _WS_EX_TRANSPARENT | _WS_EX_NOACTIVATE)

    def _position_in_corner(self):
        # Let Tk lay the new text out first, or the width is the previous one
        # and the box lands partly off the edge of the screen.
        self.root.update_idletasks()
        width = self.root.winfo_reqwidth()
        screen_width = self.root.winfo_screenwidth()
        x = MARGIN_PX if CORNER == "left" else screen_width - width - MARGIN_PX
        y = MARGIN_PX
        self.root.geometry(f"+{x}+{y}")

    def check_hotkey(self):
        """Toggle once per press, rather than on every poll while it is held."""
        down = hotkey_is_down()
        if down and not self.hotkey_was_down:
            self.toggle_visibility()
        self.hotkey_was_down = down
        self.root.after(HOTKEY_POLL_MS, self.check_hotkey)

    def toggle_visibility(self):
        self.hidden = not self.hidden
        if self.hidden:
            self.root.withdraw()
        else:
            self.root.deiconify()
            # Showing the window again can drop everything set on it once, so
            # put the whole lot back.
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            self._apply_click_through()
            self._position_in_corner()

    def read_remaining_seconds(self):
        """Seconds left, or None while the monitor isn't publishing them."""
        try:
            age = time.time() - REMAINING_TIME_FILE_PATH.stat().st_mtime
            remaining = int(REMAINING_TIME_FILE_PATH.read_text(encoding="utf-8").strip())
        except Exception:
            return None
        # A stale zero still means the time is up: the monitor writes 0 and then
        # exits to shut the machine down, so nothing refreshes the file after it.
        if remaining > 0 and age > STALE_AFTER_SECONDS:
            return None
        return remaining

    def update_label(self):
        remaining = self.read_remaining_seconds()
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
        if not self.hidden:
            self._position_in_corner()
        self.root.after(POLL_INTERVAL_MS, self.update_label)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    RemainingTimeWidget().run()
