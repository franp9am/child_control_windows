"""
Small overlay showing remaining screen time.
Displays the remaining time information content from a text file.
"""

import ctypes
import math
import sys
import threading
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


# Win32 constants. The widget sits at the very top of the z-order so it stays
# readable over whatever is open, and is styled so that being on top costs the
# child nothing: clicks pass straight through it, it never takes focus, and it
# stays out of Alt+Tab and the taskbar.
_HWND_TOPMOST = -1
_SWP_NOMOVE = 0x0002
_SWP_NOSIZE = 0x0001
_SWP_NOACTIVATE = 0x0010

_GWL_EXSTYLE = -20
_WS_EX_TRANSPARENT = 0x00000020  # mouse events go to the window underneath
_WS_EX_TOOLWINDOW = 0x00000080  # no taskbar button, no Alt+Tab entry
_WS_EX_NOACTIVATE = 0x08000000  # never steals focus from the app in use

_GA_ROOT = 2  # winfo_id() can name an inner window; this walks up to the real one

# Ctrl+Alt+H hides the widget, the same combination brings it back. Registered
# system-wide, so it works whatever else has focus.
_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_NOREPEAT = 0x4000  # holding the keys down toggles once, not repeatedly
_WM_HOTKEY = 0x0312
HOTKEY_MODIFIERS = _MOD_CONTROL | _MOD_ALT | _MOD_NOREPEAT
HOTKEY_VIRTUAL_KEY = 0x48  # 'H'
HOTKEY_POLL_MS = 100

_user32 = ctypes.windll.user32
# Spelled out because the defaults would truncate window handles (and
# _HWND_TOPMOST) to 32 bits on 64-bit Windows.
_user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
_user32.GetAncestor.restype = wintypes.HWND
_user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT)
_user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
_user32.GetWindowLongW.restype = ctypes.c_long
_user32.SetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_long)
_user32.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
_user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                wintypes.UINT, wintypes.UINT)
_user32.GetMessageW.restype = ctypes.c_int


def listen_for_hotkey(on_pressed):
    """Call on_pressed() every time the toggle shortcut is hit, forever.

    Windows delivers the hotkey to the thread that registered it, and Tk's own
    message loop would quietly drop a thread message it knows nothing about, so
    this runs its own loop and belongs on a dedicated thread. If the shortcut is
    already taken by another program it simply returns: the widget still works,
    it just cannot be hidden.
    """
    if not _user32.RegisterHotKey(None, 1, HOTKEY_MODIFIERS, HOTKEY_VIRTUAL_KEY):
        return
    message = wintypes.MSG()
    while _user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
        if message.message == _WM_HOTKEY:
            on_pressed()


class RemainingTimeWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", OPACITY)
        self.root.attributes("-topmost", True)
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
        # Set from the hotkey thread, acted on by the Tk thread: tkinter calls
        # are only safe from the thread running the main loop.
        self.toggle_requested = threading.Event()

        self.root.update_idletasks()
        self._apply_window_styles()
        self._raise_to_top()

        threading.Thread(
            target=listen_for_hotkey,
            args=(self.toggle_requested.set,),
            daemon=True,
        ).start()
        self.root.after(HOTKEY_POLL_MS, self.check_toggle_request)
        self.update_label()

    def _hwnd(self):
        return _user32.GetAncestor(self.root.winfo_id(), _GA_ROOT)

    def _apply_window_styles(self):
        hwnd = self._hwnd()
        style = _user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
        _user32.SetWindowLongW(
            hwnd,
            _GWL_EXSTYLE,
            style | _WS_EX_TRANSPARENT | _WS_EX_TOOLWINDOW | _WS_EX_NOACTIVATE,
        )

    def _position_in_corner(self):
        # Let Tk lay the new text out first, or the width is the previous one
        # and the box lands partly off the edge of the screen.
        self.root.update_idletasks()
        width = self.root.winfo_reqwidth()
        screen_width = self.root.winfo_screenwidth()
        x = MARGIN_PX if CORNER == "left" else screen_width - width - MARGIN_PX
        y = MARGIN_PX
        self.root.geometry(f"+{x}+{y}")

    def _raise_to_top(self):
        """Re-assert the top of the z-order; other programs claim it too, and
        the last one to ask wins."""
        _user32.SetWindowPos(
            self._hwnd(),
            _HWND_TOPMOST,
            0,
            0,
            0,
            0,
            _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOACTIVATE,
        )

    def check_toggle_request(self):
        if self.toggle_requested.is_set():
            self.toggle_requested.clear()
            self.toggle_visibility()
        self.root.after(HOTKEY_POLL_MS, self.check_toggle_request)

    def toggle_visibility(self):
        self.hidden = not self.hidden
        if self.hidden:
            self.root.withdraw()
        else:
            self.root.deiconify()
            # Showing the window again can drop the borderless flag and the
            # extended styles, so set the whole thing up from scratch.
            self.root.overrideredirect(True)
            self._apply_window_styles()
            self._position_in_corner()
            self._raise_to_top()

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
            self._raise_to_top()
        self.root.after(POLL_INTERVAL_MS, self.update_label)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    RemainingTimeWidget().run()
