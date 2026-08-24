import ctypes
import subprocess
import time
from ctypes import wintypes

WTS_CURRENT_SERVER = 0
WTS_USER_NAME = 5
WTS_ACTIVE = 0  # a disconnected session is not time at the screen
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# None off windows, so importing this module never breaks tests of the pure logic
_wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True) if hasattr(ctypes, "WinDLL") else None


class SessionInfo(ctypes.Structure):
    _fields_ = [("id", wintypes.DWORD), ("station", wintypes.LPWSTR), ("state", ctypes.c_int)]


def _session_user(session_id: int) -> str:
    name, size = wintypes.LPWSTR(), wintypes.DWORD()
    if not _wtsapi32.WTSQuerySessionInformationW(WTS_CURRENT_SERVER, session_id, WTS_USER_NAME,
                                                 ctypes.byref(name), ctypes.byref(size)):
        return ""
    user = name.value or ""
    _wtsapi32.WTSFreeMemory(name)
    return user


def user_by_session_id() -> dict[int, str]:
    infos, count = ctypes.POINTER(SessionInfo)(), wintypes.DWORD()
    if not _wtsapi32.WTSEnumerateSessionsW(WTS_CURRENT_SERVER, 0, 1,
                                           ctypes.byref(infos), ctypes.byref(count)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return {infos[i].id: _session_user(infos[i].id)
                for i in range(count.value) if infos[i].state == WTS_ACTIVE}
    finally:
        _wtsapi32.WTSFreeMemory(infos)


def user_logged_in(user: str) -> bool:
    try:
        return any(name.lower() == user.lower() for name in user_by_session_id().values())
    except OSError:
        return True  # a check that cannot answer must not hand out unlimited time


def notify(message: str, user: str) -> None:
    title = "Screen time"
    try:
        for session_id, name in user_by_session_id().items():
            if name.lower() == user.lower():
                # the lengths are in bytes, and the string is utf-16
                _wtsapi32.WTSSendMessageW(WTS_CURRENT_SERVER, session_id, title, len(title) * 2,
                                          message, len(message) * 2, 0, 0,
                                          ctypes.byref(wintypes.DWORD()), False)
    except OSError:
        pass


def shutdown(delay_seconds: int) -> None:
    """Blocks until the machine goes down; the undelayed repeat defeats `shutdown /a`."""
    for delay in (int(delay_seconds), 0):
        subprocess.run(["shutdown", "/s", "/f", "/t", str(delay)], creationflags=CREATE_NO_WINDOW)
        time.sleep(delay + 10)
