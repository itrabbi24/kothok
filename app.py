"""Kothok (কথক) - portable, offline, tray-based push-to-talk dictation for Windows.

Hold (or toggle) a global hotkey anywhere, speak Bangla (and/or English), and the text is
inserted where the cursor is. Everything runs locally with sherpa-onnx; no cloud APIs.

Previous version is preserved in legacy/app_v1.py.
"""
from __future__ import annotations

import ctypes
import json
import logging
import os
import queue
import re
import struct
import sys
import threading
import time
import tkinter as tk
import traceback
import wave
import winreg
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox

import numpy as np

APP_NAME = "Kothok"          # কথক - "the one who speaks"
APP_BN = "কথক"
APP_ID = "Kothok"
VERSION = "2.7.1"
WEBSITE = "https://rotexit.com"
UPDATE_REPO = "itrabbi24/kothok"   # GitHub releases are checked for new versions
UPDATE_ASSET = "Kothok-update.zip"  # app-only zip (no models) attached to every release

# UI palette - (light, dark) pairs; customtkinter picks one from the appearance mode
# (was dark only: C_BG, C_CARD, C_BORDER, C_KEY = "#0d1210", "#141b18", "#24302b", "#1b2420";
#  C_TEXT, C_MUTED = "#eef1f6", "#8b93a5")
C_BG, C_CARD = ("#f4f7f5", "#0d1210"), ("#ffffff", "#141b18")
C_BORDER, C_KEY = ("#dde5e0", "#24302b"), ("#eaf0ec", "#1b2420")
C_TEXT, C_MUTED = ("#14201b", "#eef1f6"), ("#5f6b66", "#8b93a5")
C_SEL, C_SEL_H = ("#bfe6cf", "#0f9d58"), ("#a9dcbe", "#0b7d46")   # selected segment (light tint / green)
POSITIONS = {"bottom-center": "Bottom centre", "bottom-right": "Bottom right",
             "bottom-left": "Bottom left", "top-center": "Top centre"}
THEMES = {"light": "Light", "dark": "Dark", "system": "System"}
C_ACCENT, C_ACCENT_H = "#0f9d58", "#0b7d46"   # Bangladesh green
C_GREEN, C_AMBER, C_RED, C_GREY = "#22c55e", "#f59e0b", "#ef4444", "#6b7280"

# --------------------------------------------------------------------------- paths
FROZEN = getattr(sys, "frozen", False)
ROOT = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent
MODELS = ROOT / "models"


def _data_dir() -> Path:
    """Portable first: keep config next to the exe. Fall back to %APPDATA% if read-only."""
    try:
        probe = ROOT / ".write_test"
        probe.write_text("x"); probe.unlink()
        return ROOT
    except OSError:
        d = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_ID
        d.mkdir(parents=True, exist_ok=True)
        return d


DATA = _data_dir()
CONFIG_FILE = DATA / "config.json"
LOG_FILE = DATA / "app.log"

logging.basicConfig(filename=str(LOG_FILE), level=logging.INFO, encoding="utf-8",
                    format="%(asctime)s %(levelname)s %(threadName)s: %(message)s")
log = logging.getLogger(APP_ID)

# --------------------------------------------------------------------------- win32
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
user32.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
user32.IsWindow.argtypes = (wintypes.HWND,)
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.OpenClipboard.argtypes = (wintypes.HWND,)
user32.GetClipboardData.argtypes = (wintypes.UINT,)
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
user32.SetClipboardData.restype = wintypes.HANDLE
user32.IsClipboardFormatAvailable.argtypes = (wintypes.UINT,)
user32.GetParent.argtypes = (wintypes.HWND,)
user32.GetParent.restype = wintypes.HWND
user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT)
user32.GetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int)
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
kernel32.GlobalFree.argtypes = (wintypes.HGLOBAL,)
kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
kernel32.CreateMutexW.restype = wintypes.HANDLE

WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP, WM_QUIT = 0x100, 0x101, 0x104, 0x105, 0x12
LLKHF_INJECTED = 0x10
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x2, 0x4
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x2
VK_MASK = 0xE8  # unassigned VK; used to stop Alt/Win from opening menus after a swallowed hotkey


WM_TIMER = 0x113


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


user32.GetLastInputInfo.argtypes = (ctypes.POINTER(LASTINPUTINFO),)
user32.SetTimer.argtypes = (wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p)
user32.SetTimer.restype = ctypes.c_size_t
kernel32.GetTickCount.restype = wintypes.DWORD


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)


def send_keys(events):
    """events: list of (vk, scan, flags)."""
    arr = (INPUT * len(events))()
    for i, (vk, scan, flags) in enumerate(events):
        arr[i].type = INPUT_KEYBOARD
        arr[i].u.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))


# --------------------------------------------------------------------------- keys
MOD_GROUPS = {
    "CTRL": (0x11, 0xA2, 0xA3),
    "ALT": (0x12, 0xA4, 0xA5),
    "SHIFT": (0x10, 0xA0, 0xA1),
    "WIN": (0x5B, 0x5C),
}
MOD_VK = {vk: name for name, vks in MOD_GROUPS.items() for vk in vks}
MOD_ORDER = ["CTRL", "ALT", "SHIFT", "WIN"]
KEY_NAMES = {**{chr(c): c for c in range(65, 91)}, **{str(i): 0x30 + i for i in range(10)},
             **{f"F{i}": 0x6F + i for i in range(1, 25)},
             "SPACE": 0x20, "TAB": 0x09, "CAPSLOCK": 0x14, "INSERT": 0x2D, "HOME": 0x24, "END": 0x23,
             "PAGEUP": 0x21, "PAGEDOWN": 0x22, "PAUSE": 0x13, "SCROLLLOCK": 0x91,
             "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, "\\": 0xDC, ";": 0xBA,
             "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
             **{f"NUM{i}": 0x60 + i for i in range(10)}}
VK_TO_NAME = {v: k for k, v in KEY_NAMES.items()}


def parse_hotkey(text: str):
    """'ALT+R' -> (frozenset({'ALT'}), 0x52)."""
    parts = [p.strip().upper() for p in text.split("+") if p.strip()]
    mods = frozenset(p for p in parts if p in MOD_GROUPS)
    keys = [p for p in parts if p not in MOD_GROUPS]
    if len(keys) != 1:
        raise ValueError("Hotkey needs exactly one non-modifier key, e.g. ALT+R or F9")
    k = keys[0]
    if k in KEY_NAMES:
        vk = KEY_NAMES[k]
    elif re.fullmatch(r"VK_[0-9A-F]{2}", k):
        vk = int(k[3:], 16)
    else:
        raise ValueError(f"Unknown key: {k}")
    return mods, vk


def format_hotkey(mods, vk) -> str:
    name = VK_TO_NAME.get(vk, f"VK_{vk:02X}")
    return "+".join([m for m in MOD_ORDER if m in mods] + [name])


class KeyboardHook:
    """Global low-level keyboard hook. Swallows the hotkey so it never reaches the target app."""

    def __init__(self, on_event):
        self.on_event = on_event          # called with "press" / "release" / ("captured", str)
        self.mods: frozenset = frozenset()
        self.vk = 0
        self.held: set = set()            # modifier names currently physically down
        self.active = False               # hotkey main key currently down (swallowed)
        self.capture = False
        self.thread_id = None
        self._proc = HOOKPROC(self._hook)  # keep reference alive
        self._thread = threading.Thread(target=self._run, name="KeyboardHook", daemon=True)

    def set_hotkey(self, text):
        self.mods, self.vk = parse_hotkey(text)

    def start(self):
        self._thread.start()

    def stop(self):
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)

    def _install(self):
        hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, kernel32.GetModuleHandleW(None), 0)
        if not hook:
            log.error("SetWindowsHookEx failed: %s", ctypes.get_last_error())
        return hook

    def _run(self):
        # Windows silently removes a low-level hook whose callback is too slow (LowLevelHooksTimeout),
        # which happens at boot / resume from sleep while the models load and the PC is busy. Nothing
        # tells us, so a timer checks every few seconds: if the user typed (GetLastInputInfo moved)
        # but our hook saw nothing for a while, the hook is reinstalled. Also reinstalled periodically.
        self.thread_id = kernel32.GetCurrentThreadId()
        hook = self._install()
        installed = time.monotonic()
        self.last_seen = kernel32.GetTickCount()
        user32.SetTimer(None, 0, 3000, None)
        msg = wintypes.MSG()
        lii = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message != WM_TIMER:
                continue
            stale = False
            if user32.GetLastInputInfo(ctypes.byref(lii)):
                # input happened >4 s after the last event our hook saw -> suspicious
                stale = ((lii.dwTime - self.last_seen) & 0xFFFFFFFF) < 0x7FFFFFFF and \
                        ((lii.dwTime - self.last_seen) & 0xFFFFFFFF) > 4000
            if not hook or (stale and time.monotonic() - installed > 10) or time.monotonic() - installed > 600:
                if hook:
                    user32.UnhookWindowsHookEx(hook)
                hook = self._install()
                installed = time.monotonic()
                self.last_seen = kernel32.GetTickCount()
                # (stale also fires after pure mouse use - reinstalling is cheap and harmless)
                log.debug("keyboard hook reinstalled")
        if hook:
            user32.UnhookWindowsHookEx(hook)

    def _hook(self, code, wparam, lparam):
        self.last_seen = kernel32.GetTickCount()
        try:
            if code == 0:
                kb = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if not kb.flags & LLKHF_INJECTED and self._handle(kb.vkCode, wparam):
                    return 1
        except Exception:  # never let an exception escape into Windows
            log.exception("hook error")
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _handle(self, vk, wparam) -> bool:
        down = wparam in (WM_KEYDOWN, WM_SYSKEYDOWN)
        up = wparam in (WM_KEYUP, WM_SYSKEYUP)
        if vk in MOD_VK:
            (self.held.add if down else self.held.discard)(MOD_VK[vk])
            return False
        if self.capture and down:
            if vk == 0x1B and not self.held:  # Esc cancels capture
                self.capture = False
                self.on_event(("captured", None))
                return True
            self.capture = False
            self.on_event(("captured", format_hotkey(frozenset(self.held), vk)))
            return True
        if vk != self.vk:
            return False
        if down:
            if self.active:
                if user32.GetAsyncKeyState(vk) & 0x8000:
                    return True  # auto-repeat
                # the key-up was missed (sleep, lock screen, hook dropped) - finish the old press first
                self.active = False
                self.on_event("release")
            # Re-read the real modifier state: a key-up missed during sleep/lock/UAC used to leave
            # e.g. ALT stuck in `held`, and then the hotkey never matched again.
            self.held = {name for v, name in MOD_VK.items() if user32.GetAsyncKeyState(v) & 0x8000}
            if frozenset(self.held) == self.mods:
                self.active = True
                if self.held & {"ALT", "WIN"}:
                    send_keys([(VK_MASK, 0, 0), (VK_MASK, 0, KEYEVENTF_KEYUP)])
                self.on_event("press")
                return True
            return False
        if up and self.active:
            self.active = False
            self.on_event("release")
            return True
        return False


def modifiers_down() -> bool:
    return any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x10, 0x11, 0x12, 0x5B, 0x5C))


# --------------------------------------------------------------------------- clipboard / output
def _open_clipboard():
    for _ in range(20):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.025)
    return False


def clipboard_get():
    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT) or not _open_clipboard():
        return None
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        p = kernel32.GlobalLock(h)
        try:
            return ctypes.wstring_at(p) if p else None
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def clipboard_set(text: str) -> bool:
    data = text.encode("utf-16-le") + b"\x00\x00"
    if not _open_clipboard():
        return False
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        kernel32.GlobalUnlock(h)
        if not user32.SetClipboardData(CF_UNICODETEXT, h):
            kernel32.GlobalFree(h)
            return False
        return True
    finally:
        user32.CloseClipboard()


def type_unicode(text: str):
    events = []
    raw = text.encode("utf-16-le")
    for i in range(0, len(raw), 2):
        unit = struct.unpack("<H", raw[i:i + 2])[0]
        events += [(0, unit, KEYEVENTF_UNICODE), (0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    # one character (down+up) at a time: some apps drop bursts of injected unicode input
    for i in range(0, len(events), 2):
        send_keys(events[i:i + 2])
        time.sleep(0.012)


def insert_text(text: str, target_hwnd, method: str, restore_clipboard: bool):
    # Wait for the user to let go of Ctrl/Alt/Shift/Win, otherwise Ctrl+V becomes Ctrl+Alt+V etc.
    deadline = time.time() + 2.0
    while modifiers_down() and time.time() < deadline:
        time.sleep(0.02)
    if target_hwnd and user32.IsWindow(target_hwnd) and user32.GetForegroundWindow() != target_hwnd:
        user32.SetForegroundWindow(target_hwnd)
        time.sleep(0.08)
    if method == "type":
        type_unicode(text)
        return
    previous = clipboard_get() if restore_clipboard else None
    if not clipboard_set(text):
        log.warning("clipboard busy - falling back to typing")
        type_unicode(text)
        return
    time.sleep(0.03)
    send_keys([(0x11, 0, 0), (0x56, 0, 0), (0x56, 0, KEYEVENTF_KEYUP), (0x11, 0, KEYEVENTF_KEYUP)])
    if previous is not None:
        time.sleep(0.6)  # give the target app time to read the clipboard
        clipboard_set(previous)


# --------------------------------------------------------------------------- config
DEFAULTS = {
    "hotkey": "ALT+R",
    "mode": "hold",              # hold | toggle
    "engine": "mixed",           # mixed (Bangla + English) | bangla (fast, Bangla only)
                                 # ("whisper" = old turbo engine, disabled - see WhisperEngine)
    "language": "auto",          # whisper only: auto (Bangla+English mixed) | bn | en
    "device": "",                # "" = system default microphone
    "output": "paste",           # paste | type
    "restore_clipboard": True,
    "trailing_space": True,
    "word_fixes": "",            # one "wrong = right" per line, applied to every dictation
    "sounds": True,
    "autostart": False,
    "auto_update": True,         # silently download + install new GitHub releases
    "theme": "light",            # light | dark | system
    "popup_position": "bottom-center",  # where the listening popup appears (see POSITIONS)
    "first_run": True,
}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except FileNotFoundError:
        pass
    except Exception:
        log.exception("bad config, using defaults")
    if cfg.get("engine") not in ("mixed", "bangla"):
        cfg["engine"] = "mixed"
    return cfg


def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_command():
    if FROZEN:
        return f'"{sys.executable}" --tray'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pyw if pyw.exists() else sys.executable}" "{Path(__file__).resolve()}" --tray'


def set_autostart(enabled: bool):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, APP_ID, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, APP_ID)
            except FileNotFoundError:
                pass


# --------------------------------------------------------------------------- auto update
def _ver(text: str):
    return tuple(int(n) for n in re.findall(r"\d+", text)[:3]) or (0,)


class Updater:
    """Checks GitHub releases in the background. A newer release's app-only zip is downloaded and
    unpacked into a staging folder; the app swaps the files in (and restarts) once the user is idle.
    Models and config.json are never touched."""

    CHECK_EVERY = 6 * 3600

    def __init__(self, app):
        self.app = app
        self.staging = DATA / "_update"
        self.ready = None   # (version, folder with the new files)

    @staticmethod
    def supported():
        # only the portable exe, and only when its folder is writable (config lives next to it)
        return FROZEN and DATA == ROOT

    def start(self):
        if self.supported():
            threading.Thread(target=self._loop, name="Updater", daemon=True).start()

    def _loop(self):
        time.sleep(90)  # let the engine load first
        while True:
            if self.app.cfg.get("auto_update", True) and not self.ready:
                try:
                    self.check()
                except Exception as exc:
                    log.info("update check failed: %s", exc)
            time.sleep(self.CHECK_EVERY)

    def check(self):
        import urllib.request
        import zipfile
        req = urllib.request.Request(f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest",
                                     headers={"User-Agent": f"{APP_ID}/{VERSION}",
                                              "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            rel = json.loads(r.read().decode("utf-8"))
        latest = rel.get("tag_name", "")
        if rel.get("draft") or rel.get("prerelease") or _ver(latest) <= _ver(VERSION):
            return
        asset = next((a for a in rel.get("assets", []) if a.get("name") == UPDATE_ASSET), None)
        if not asset:
            log.info("release %s has no %s", latest, UPDATE_ASSET)
            return
        log.info("downloading update %s", latest)
        import shutil
        if self.staging.exists():
            shutil.rmtree(self.staging, ignore_errors=True)
        self.staging.mkdir(parents=True)
        zpath = self.staging / UPDATE_ASSET
        dl = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": f"{APP_ID}/{VERSION}"})
        with urllib.request.urlopen(dl, timeout=60) as r, open(zpath, "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
        if asset.get("size") and zpath.stat().st_size != asset["size"]:
            raise OSError("download incomplete")
        with zipfile.ZipFile(zpath) as z:
            z.extractall(self.staging / "new")
        zpath.unlink()
        exe = next((self.staging / "new").rglob("Kothok.exe"), None)
        if not exe:
            raise OSError("Kothok.exe missing in update")
        self.ready = (latest, exe.parent)
        log.info("update %s ready in %s", latest, exe.parent)
        self.app.ui.put(("update", latest))

    def apply(self):
        """Write a tiny batch file that waits for us to exit, copies the new files, and restarts."""
        import subprocess
        import tempfile
        version, src = self.ready
        script = Path(tempfile.gettempdir()) / f"kothok-update-{os.getpid()}.cmd"
        lines = [
            "@echo off",
            ":wait",
            f'tasklist /FI "PID eq {os.getpid()}" | find "{os.getpid()}" >nul && (timeout /t 1 /nobreak >nul & goto wait)',
            f'robocopy "{src}" "{ROOT}" /E /XD models /XF config.json app.log /R:10 /W:1 /NFL /NDL /NJH /NJS >nul',
            f'rmdir /s /q "{self.staging}"',
            f'start "" "{ROOT / "Kothok.exe"}" --tray',
            'del "%~f0"',
        ]
        script.write_text("".join(x + chr(13) + chr(10) for x in lines), encoding="utf-8")
        subprocess.Popen(["cmd.exe", "/c", str(script)], creationflags=0x08000000 | 0x00000008,  # no window, detached
                         close_fds=True)
        log.info("installing update %s and restarting", version)


# --------------------------------------------------------------------------- speech engines
def _threads():
    return max(1, min(4, (os.cpu_count() or 2) // 2))


def _find(folder: Path, pattern: str):
    hits = sorted(folder.glob(pattern))
    return hits[0] if hits else None


ENGINE_LABELS = {
    "mixed": "Bangla + English",
    # "whisper": "Bangla + English (best quality)",  # disabled: turbo engine, see WhisperEngine
    "bangla": "Bangla streaming (fast, Bangla only)",
}
LANG_LABELS = {"auto": "Auto — Bangla + English (recommended)", "bn": "Bangla only", "en": "English only"}


def engine_available(name):
    if name == "mixed":
        d = MODELS / "lid"
        return engine_available("bangla") and bool(d.exists() and _find(d, "*encoder*.onnx")
                                                   and _find(d, "*decoder*.onnx") and _find(d, "*tokens.txt"))
    if name == "bangla":
        return all((MODELS / "bn" / f).exists() for f in ("encoder.onnx", "decoder.onnx", "joiner.onnx", "tokens.txt"))
    d = MODELS / "whisper"
    return bool(d.exists() and _find(d, "*encoder*.onnx") and _find(d, "*decoder*.onnx") and _find(d, "*tokens.txt"))


class BanglaEngine:
    """Streaming zipformer (Vosk-derived) - low latency, live preview, Bangla script only."""

    def __init__(self, _cfg):
        import sherpa_onnx
        d = MODELS / "bn"
        self.rec = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=str(d / "tokens.txt"), encoder=str(d / "encoder.onnx"),
            decoder=str(d / "decoder.onnx"), joiner=str(d / "joiner.onnx"),
            num_threads=_threads(), sample_rate=16000, feature_dim=80,
            # beam search (was greedy_search) keeps 4 hypotheses -> fewer wrong letters/words, small CPU cost
            decoding_method="modified_beam_search", max_active_paths=4, enable_endpoint_detection=True,
            rule1_min_trailing_silence=2.4, rule2_min_trailing_silence=1.0, rule3_min_utterance_length=30,
        )

    def session(self):
        return _BanglaSession(self.rec)


class _BanglaSession:
    def __init__(self, rec):
        self.rec, self.stream, self.done, self.sr = rec, rec.create_stream(), [], 16000

    def _current(self):
        return self.rec.get_result(self.stream).strip()

    def feed(self, sr, samples):
        self.sr = sr
        self.stream.accept_waveform(sr, samples)
        while self.rec.is_ready(self.stream):
            self.rec.decode_stream(self.stream)
        if self.rec.is_endpoint(self.stream):
            t = self._current()
            if t:
                self.done.append(t)
            self.rec.reset(self.stream)

    def partial(self):
        return " ".join(self.done + [self._current()]).strip()

    def finish(self):
        self.stream.accept_waveform(self.sr, np.zeros(int(self.sr * 0.4), dtype=np.float32))
        self.stream.input_finished()
        while self.rec.is_ready(self.stream):
            self.rec.decode_stream(self.stream)
        t = self._current()
        if t:
            self.done.append(t)
        return " ".join(self.done)


class WhisperEngine:
    """Whisper large-v3-turbo (int8).
    DISABLED (2026-11-10): sherpa-onnx turns each token into text separately, so Bangla letters
    (split across byte-level tokens) are dropped -> empty output; auto language-ID also picked
    Hindi/Gujarati for Bangla speech, and output is truncated. Replaced by MixedEngine. Kept for reference."""
    CHUNK_SECONDS = 28

    def __init__(self, cfg):
        import sherpa_onnx
        d = MODELS / "whisper"
        enc = _find(d, "*encoder.int8.onnx") or _find(d, "*encoder*.onnx")
        dec = _find(d, "*decoder.int8.onnx") or _find(d, "*decoder*.onnx")
        lang = {"auto": ""}.get(cfg["language"], cfg["language"])
        self.rec = sherpa_onnx.OfflineRecognizer.from_whisper(
            encoder=str(enc), decoder=str(dec), tokens=str(_find(d, "*tokens.txt")),
            language=lang, task="transcribe", num_threads=max(2, (os.cpu_count() or 2) - 1),
            tail_paddings=600,
        )

    def session(self):
        return _WhisperSession(self.rec, self.CHUNK_SECONDS)


class _WhisperSession:
    def __init__(self, rec, chunk):
        self.rec, self.chunk, self.parts, self.sr = rec, chunk, [], 16000

    def feed(self, sr, samples):
        self.sr = sr
        self.parts.append(samples)

    def partial(self):
        return None

    def finish(self):
        if not self.parts:
            return ""
        audio = np.concatenate(self.parts)
        # Whisper hallucinates on silence ("Thank you", subtitles credits...) - skip quiet / tiny clips
        if len(audio) < self.sr * 0.35 or float(np.sqrt(np.mean(audio ** 2))) < 0.003:
            log.info("skipped: too short/quiet (%.2fs)", len(audio) / self.sr)
            return ""
        peak = float(np.max(np.abs(audio)))
        if 0 < peak < 0.5:
            audio = audio * min(4.0, 0.7 / peak)  # gentle normalisation for quiet mics
        out, step = [], int(self.sr * self.chunk)
        for i in range(0, len(audio), step):
            s = self.rec.create_stream()
            s.accept_waveform(self.sr, audio[i:i + step].astype(np.float32))
            self.rec.decode_stream(s)
            out.append(s.result.text.strip())
        return " ".join(t for t in out if t)


def to_16k(sr, x):
    if sr == 16000:
        return x.astype(np.float32)
    n = int(len(x) * 16000 / sr)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def split_on_pauses(x, sr=16000, min_pause=0.36):
    """Cut a recording into phrases at pauses (simple adaptive energy VAD)."""
    hop = int(sr * 0.03)
    n = len(x) // hop
    if n == 0:
        return []
    rms = np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    voiced = rms > max(float(np.percentile(rms, 15)) * 3, 0.006)
    need = int(min_pause / 0.03)
    spans, start, silent = [], None, 0
    for i, v in enumerate(voiced):
        if v:
            start = i if start is None else start
            silent = 0
        elif start is not None:
            silent += 1
            if silent >= need:
                spans.append((start, i - silent + 1)); start, silent = None, 0
    if start is not None:
        spans.append((start, n))
    return [x[max(0, (a - 6) * hop): min(len(x), (b + 10) * hop)] for a, b in spans if (b - a) * 0.03 >= 0.25]


class MixedEngine:
    """Bangla + English, fully offline.
    Bangla is written by the streaming Bangla model (accurate, Bangla script). Each phrase
    (split at short pauses) is language-checked by a small multilingual model (whisper base);
    phrases detected as English are written in English with punctuation."""

    def __init__(self, cfg):
        import sherpa_onnx
        self.bangla = BanglaEngine(cfg)
        d = MODELS / "lid"
        enc = _find(d, "*encoder.int8.onnx") or _find(d, "*encoder*.onnx")
        dec = _find(d, "*decoder.int8.onnx") or _find(d, "*decoder*.onnx")
        self.en = sherpa_onnx.OfflineRecognizer.from_whisper(
            encoder=str(enc), decoder=str(dec), tokens=str(_find(d, "*tokens.txt")),
            language="", task="transcribe", num_threads=max(2, (os.cpu_count() or 2) - 1))

    def session(self):
        return _MixedSession(self)


class _MixedSession:
    def __init__(self, eng):
        self.eng, self.live, self.parts = eng, eng.bangla.session(), []

    def feed(self, sr, samples):
        self.live.feed(sr, samples)          # live Bangla preview in the overlay
        self.parts.append(to_16k(sr, samples))

    def partial(self):
        return self.live.partial()

    def _bangla(self, seg):
        s = self.eng.bangla.session()
        s.feed(16000, seg)
        return s.finish()

    def finish(self):
        if not self.parts:
            return ""
        audio = np.concatenate(self.parts)
        out = []
        for seg in split_on_pauses(audio):
            s = self.eng.en.create_stream()
            s.accept_waveform(16000, seg)
            self.eng.en.decode_stream(s)
            lang = s.result.lang.strip("<|> ")
            english = s.result.text.strip()
            if lang == "en" and re.search(r"[A-Za-z]", english):
                out.append(clean_text(english))
                log.info("phrase %.1fs -> en", len(seg) / 16000)
            else:
                out.append(self._bangla(seg))
                log.info("phrase %.1fs -> bn (detected %s)", len(seg) / 16000, lang)
        text = " ".join(t for t in out if t)
        if not text:  # VAD found nothing usable - fall back to the live Bangla result
            text = self.live.finish()
        return text


# "whisper": WhisperEngine disabled - see its docstring
ENGINES = {"mixed": MixedEngine, "bangla": BanglaEngine}

HALLUCINATIONS = re.compile(
    r"^(thank you\.?|thanks for watching!?|subtitles? by.*|ধন্যবাদ।?|\[.*\]|\(.*\))$", re.IGNORECASE)


def apply_word_fixes(text: str, rules: str) -> str:
    """User dictionary: lines like "কতক = কথক" or "rotex it = rotexit". Whole-word, case-insensitive."""
    for line in (rules or "").splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        wrong, right = (p.strip() for p in line.split("=", 1))
        if wrong:
            text = re.sub(r"(?<!\w)" + re.escape(wrong) + r"(?!\w)", lambda m: right, text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if HALLUCINATIONS.fullmatch(text):
        return ""
    return text


# --------------------------------------------------------------------------- sounds / icons
def _make_tone(path: Path, freqs):
    sr = 22050
    chunks = []
    for f in freqs:
        t = np.arange(int(sr * 0.07)) / sr
        env = np.minimum(1, np.minimum(t, t[::-1]) * 200)
        chunks.append(0.25 * np.sin(2 * np.pi * f * t) * env)
    data = (np.concatenate(chunks) * 32767).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(data)


SOUND_DIR = Path(os.environ.get("TEMP", str(DATA))) / APP_ID
SOUNDS = {"start": (660, 990), "stop": (990, 660), "error": (300, 220)}


def play(name):
    try:
        import winsound
        p = SOUND_DIR / f"{name}.wav"
        if not p.exists():
            SOUND_DIR.mkdir(parents=True, exist_ok=True)
            _make_tone(p, SOUNDS[name])
        winsound.PlaySound(str(p), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        log.exception("sound")


def make_icon(state="idle", size=64):
    """Kothok logo v2: green gradient tile, white speech bubble with sound-wave bars, red sun dot.
    State: idle=green bars + red sun, rec=red bars + white-ringed sun, busy=amber, error=grey."""
    from PIL import Image, ImageDraw
    sun = {"idle": "#f42a41", "rec": "#ff1f3d", "busy": "#f59e0b", "error": "#9ca3af"}[state]
    bars = {"idle": "#006a4e", "rec": "#e11d2e", "busy": "#b45309", "error": "#6b7280"}[state]
    s = 512
    top, bottom = (0x14, 0xa8, 0x63), (0x00, 0x5c, 0x43)
    grad = Image.new("RGBA", (1, s))
    for y in range(s):
        t = y / (s - 1)
        grad.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,))
    grad = grad.resize((s, s))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((8, 8, s - 8, s - 8), radius=118, fill=255)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    # speech bubble with a tail at the bottom left
    d.rounded_rectangle((88, 132, 424, 372), radius=84, fill="white")
    d.polygon([(150, 340), (122, 430), (236, 362)], fill="white")
    # sound wave
    for cx, h in ((172, 56), (214, 112), (256, 160), (298, 112), (340, 56)):
        d.rounded_rectangle((cx - 13, 252 - h / 2, cx + 13, 252 + h / 2), radius=13, fill=bars)
    # red sun (Bangladesh flag)
    if state == "rec":
        d.ellipse((350, 52, 466, 168), fill="white")
    d.ellipse((362, 64, 454, 156), fill=sun)
    return img.resize((size, size), Image.LANCZOS)


def make_icon_v1(state="idle", size=64):
    """Kept for reference (replaced by the speech-bubble logo above).
    Kothok logo: flag-green tile, red sun, white microphone, shapla petals.
    State tints the sun: idle=red (flag), rec=bright red + white ring, busy=amber, error=grey."""
    from PIL import Image, ImageDraw
    sun = {"idle": "#f42a41", "rec": "#ff1f3d", "busy": "#f59e0b", "error": "#6b7280"}[state]
    s = 512
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, s - 8, s - 8), radius=112, fill="#006a4e")
    # shapla (water lily) petals fanning out from the base, behind the sun
    import math
    base_x, base_y = 256, 452
    for ang, length, colour in ((-64, 250, "#0b7a5a"), (64, 250, "#0b7a5a"),
                                (-34, 300, "#12936c"), (34, 300, "#12936c"), (0, 330, "#18a679")):
        a = math.radians(ang)
        pts = []
        for i in range(41):  # vesica petal: pointed at both ends
            t = i / 40
            half = 58 * math.sin(math.pi * t)
            along = length * t
            for sign in (1,):
                pts.append((along, sign * half))
        pts += [(along, -half) for along, half in reversed(pts)]
        d.polygon([(base_x + x * math.sin(a) + y * math.cos(a), base_y - x * math.cos(a) + y * math.sin(a))
                   for x, y in pts], fill=colour)
    if state == "rec":
        d.ellipse((76, 56, 436, 416), outline="#ffffff", width=14)
    d.ellipse((106, 86, 406, 386), fill=sun)
    w = "white"
    d.rounded_rectangle((216, 136, 296, 276), radius=40, fill=w)
    d.arc((176, 196, 336, 316), 0, 180, fill=w, width=18)
    d.line((256, 316, 256, 352), fill=w, width=18)
    d.rounded_rectangle((212, 346, 300, 362), radius=8, fill=w)
    return img.resize((size, size), Image.LANCZOS)


# --------------------------------------------------------------------------- overlay
class Overlay:
    """Small floating pill near the bottom of the screen. Never takes keyboard focus."""
    W, H = 360, 46
    KEY = "#010203"

    def __init__(self, root):
        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.configure(bg=self.KEY)
        self.top.attributes("-transparentcolor", self.KEY)
        self.c = tk.Canvas(self.top, width=self.W, height=self.H, bg=self.KEY, highlightthickness=0)
        self.c.pack()
        self._pill(2, 2, self.W - 2, self.H - 2, 21, fill="#1f2430")
        self.dot = self.c.create_oval(16, 16, 30, 30, fill="#e53935", outline="")
        self.label = self.c.create_text(42, self.H // 2, anchor="w", fill="white", font=("Nirmala UI", 11),
                                        text="", width=self.W - 130)
        # live sound bars on the right, driven by the microphone level while listening
        self.level, self.heights = 0.0, [3.0] * 5
        self.bars = [self.c.create_rectangle(0, 0, 0, 0, fill="#22c55e", outline="") for _ in range(5)]
        # was always bottom centre: sw, sh = screen size; geometry(+{(sw - W) // 2}+{sh - H - 90})
        self.place("bottom-center")
        self.top.update_idletasks()
        self.hwnd = user32.GetParent(self.top.winfo_id()) or self.top.winfo_id()
        GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST = -20, 0x08000000, 0x80, 0x8
        ex = user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST)
        self.visible = False
        self.pulse_on = True
        self.hide()
        self._tick()
        self._animate()

    def place(self, position):
        """Put the popup at a corner/edge of the work area (screen minus taskbar)."""
        r = wintypes.RECT()
        if not user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0):  # SPI_GETWORKAREA
            r.left, r.top = 0, 0
            r.right, r.bottom = self.top.winfo_screenwidth(), self.top.winfo_screenheight()
        m = 16
        x = {"bottom-right": r.right - self.W - m, "bottom-left": r.left + m}.get(
            position, (r.left + r.right - self.W) // 2)
        y = r.top + m if position == "top-center" else r.bottom - self.H - (m if position in ("bottom-right", "bottom-left") else 40)
        self.top.geometry(f"{self.W}x{self.H}+{x}+{y}")
        if getattr(self, "hwnd", None):  # Tk ignores geometry changes once Win32 has shown the window
            SWP_NOSIZE, SWP_NOZORDER, SWP_NOACTIVATE = 1, 4, 0x10
            user32.SetWindowPos(self.hwnd, None, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)

    def _pill(self, x1, y1, x2, y2, r, **kw):
        c = self.c
        c.create_oval(x1, y1, x1 + 2 * r, y2, outline="", **kw)
        c.create_oval(x2 - 2 * r, y1, x2, y2, outline="", **kw)
        c.create_rectangle(x1 + r, y1, x2 - r, y2, outline="", **kw)

    def show(self, text, colour="#e53935"):
        self.c.itemconfigure(self.label, text=text)
        self.c.itemconfigure(self.dot, fill=colour)
        self.colour = colour
        if not self.visible:
            SW_SHOWNOACTIVATE, HWND_TOPMOST, SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 4, -1, 2, 1, 0x10
            user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            self.visible = True

    def text(self, text):
        """Live preview: one line only, showing the newest words (it used to wrap and spill out of the pill)."""
        from tkinter import font as tkfont
        if not hasattr(self, "_font"):
            self._font = tkfont.Font(family="Nirmala UI", size=11)
        room = self.W - 140
        text = " ".join(text.split())
        if self._font.measure(text) > room:
            words = text.split(" ")
            while len(words) > 1 and self._font.measure("… " + " ".join(words)) > room:
                words.pop(0)
            text = "… " + " ".join(words)
        self.c.itemconfigure(self.label, text=text)

    def hide(self):
        user32.ShowWindow(self.hwnd, 0)
        self.visible = False

    def _animate(self):
        import random
        listening = self.visible and getattr(self, "colour", "") == "#e53935"
        level = min(1.0, self.level * 12) if listening else 0.0
        for i, bar in enumerate(self.bars):
            if not listening:
                self.c.coords(bar, 0, 0, 0, 0)
                continue
            shape = (0.55, 0.85, 1.0, 0.85, 0.55)[i]
            target = 3 + 24 * level * shape * random.uniform(0.6, 1.0)
            self.heights[i] += (target - self.heights[i]) * 0.45
            h, x = self.heights[i], self.W - 78 + i * 11
            self.c.coords(bar, x, self.H / 2 - h / 2, x + 5, self.H / 2 + h / 2)
        self.top.after(50, self._animate)

    def _tick(self):
        if self.visible:
            self.pulse_on = not self.pulse_on
            self.c.itemconfigure(self.dot, fill=self.colour if self.pulse_on else "#1f2430")
        self.top.after(450, self._tick)


# --------------------------------------------------------------------------- app
class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.cfg = load_config()
        self.ui = queue.Queue()
        self.engine = None
        self.engine_name = None
        self.engine_error = None
        self.loading = False
        self.recording = False
        self.busy = False
        self.busy_since = 0.0
        self.stream = None
        self.audio_q = None
        self.started_at = 0.0
        self.target = None
        self.tray = None
        self.history = []
        self.paused = False
        self.last_used = time.time()
        self.updater = Updater(self)

        self.overlay = Overlay(root)
        self.overlay.place(self.cfg.get("popup_position", "bottom-center"))
        self.hook = KeyboardHook(lambda ev: self.ui.put(("hook", ev)))
        try:
            self.hook.set_hotkey(self.cfg["hotkey"])
        except ValueError:
            self.cfg["hotkey"] = DEFAULTS["hotkey"]; self.hook.set_hotkey(self.cfg["hotkey"])
        self.hook.start()

        self.build_window()
        self.create_tray()
        self.load_engine_async()
        root.protocol("WM_DELETE_WINDOW", self.hide_window)
        root.after(20, self.pump)
        self.updater.start()
        # Opened by the user -> show the window. Started with Windows (--tray) -> stay in the tray, but say so.
        # (was: window only on first run, otherwise straight to the tray with no message)
        self.tray_hint_shown = False
        if self.cfg.get("first_run") or "--tray" not in sys.argv:
            self.cfg["first_run"] = False; self.persist()
            self.show_window()
        else:
            root.withdraw()
            root.after(2500, lambda: self.notify(f"কথক চালু আছে। {self.talk_hint_bn()}। "
                                                  "সেটিংস খুলতে ঘড়ির পাশের icon-এ ক্লিক করুন।"))
        if self.cfg.get("autostart"):
            try:
                set_autostart(True)  # refresh the startup entry (older versions had no --tray)
            except OSError:
                pass

    # ---------------------------------------------------------------- engine
    def load_engine_async(self):
        name = self.cfg["engine"]
        if not engine_available(name):
            other = "bangla" if name == "mixed" else "mixed"
            if engine_available(other):
                name = other
            else:
                self.engine, self.engine_error = None, "No speech model found in the 'models' folder."
                self.set_status(self.engine_error, "error")
                return
        self.loading = True
        self.engine = None
        self.set_status(f"Loading {ENGINE_LABELS[name]} ...", "busy")

        def work():
            try:
                t = time.time()
                eng = ENGINES[name](dict(self.cfg))
                log.info("loaded %s in %.1fs", name, time.time() - t)
                self.ui.put(("engine", (name, eng, None)))
            except Exception as exc:
                log.exception("engine load failed")
                self.ui.put(("engine", (name, None, str(exc))))

        threading.Thread(target=work, name="EngineLoad", daemon=True).start()

    # ---------------------------------------------------------------- event pump (Tk thread)
    def pump(self):
        try:
            while True:
                kind, payload = self.ui.get_nowait()
                self.handle(kind, payload)
        except queue.Empty:
            pass
        except Exception:
            log.exception("ui handler")
        self.root.after(20, self.pump)

    def handle(self, kind, payload):
        if kind == "hook":
            if self.paused and not isinstance(payload, tuple):
                return
            if isinstance(payload, tuple):
                self.on_captured(payload[1])
            elif payload == "press":
                if self.cfg["mode"] == "toggle":
                    self.stop_recording() if self.recording else self.start_recording()
                else:
                    self.start_recording()
            elif payload == "release" and self.cfg["mode"] == "hold":
                self.stop_recording()
        elif kind == "engine":
            name, eng, err = payload
            self.loading = False
            self.engine, self.engine_name, self.engine_error = eng, name, err
            if err:
                self.set_status(f"Model failed to load: {err}", "error")
            else:
                self.set_status(f"Ready — {self.hotkey_hint()}  •  {ENGINE_LABELS[name]}", "idle")
        elif kind == "partial":
            if self.recording:
                self.overlay.text(payload)
        elif kind == "result":
            self.busy = False
            text, err = payload
            self.overlay.hide()
            if err:
                self.set_status(f"Error: {err}", "idle"); self.notify(err)
                if self.cfg["sounds"]: play("error")
            elif text:
                self.add_history(text)
                self.set_status(f"Inserted {len(text)} characters - {self.hotkey_hint()}", "idle")
            else:
                self.set_status(f"Nothing heard - {self.hotkey_hint()}", "idle")
        elif kind == "update":
            self.install_update_when_idle()
        elif kind == "tray":
            payload()

    # ---------------------------------------------------------------- recording
    def talk_hint_bn(self):
        key = self.cfg["hotkey"].replace("+", " + ")
        return f"কথা বলতে {key} চেপে ধরুন" if self.cfg["mode"] == "hold" else f"কথা বলতে {key} একবার চাপুন"

    def hotkey_hint(self):
        return ("hold " if self.cfg["mode"] == "hold" else "press ") + self.cfg["hotkey"]

    def start_recording(self):
        if self.busy and time.time() - self.busy_since > 60:
            log.warning("previous dictation stuck for >60 s - resetting")  # never lock the hotkey forever
            self.busy = False
        if self.recording or self.busy:
            return
        self.last_used = time.time()
        if not self.engine:
            msg = "Model is still loading, please wait..." if self.loading else (self.engine_error or "No model")
            self.overlay.show(msg, "#f59e0b"); self.root.after(1800, self.overlay.hide)
            return
        import sounddevice as sd
        self.target = user32.GetForegroundWindow()
        self.audio_q = queue.Queue()
        device = self.cfg["device"] or None
        q = self.audio_q

        def open_stream(dev):
            info = sd.query_devices(dev, "input")
            sr = int(info["default_samplerate"]) or 16000
            st = sd.InputStream(device=dev, samplerate=sr, channels=1, dtype="float32", blocksize=int(sr * 0.1),
                                callback=lambda data, frames, t, status: self.on_audio(q, sr, data))
            st.start()
            return st

        try:
            try:
                self.stream = open_stream(device)
            except Exception:
                # PortAudio keeps the device list from when it started; after sleep/reboot, a mic
                # (re)plugged or a USB/Bluetooth headset reconnecting it is stale. Re-scan and retry,
                # falling back to the system default if the chosen mic is gone.
                log.warning("microphone open failed, re-scanning audio devices", exc_info=True)
                sd._terminate(); sd._initialize()
                try:
                    self.stream = open_stream(device)
                except Exception:
                    if device is None:
                        raise
                    self.stream = open_stream(None)
        except Exception as exc:
            log.exception("microphone")
            self.stream = None
            self.overlay.show(f"Microphone error: {exc}", "#6b7280"); self.root.after(3000, self.overlay.hide)
            if self.cfg["sounds"]: play("error")
            return
        self.recording = True
        self.started_at = time.time()
        if self.cfg["sounds"]: play("start")
        self.overlay.show("শুনছি…")
        self.set_tray_state("rec")
        threading.Thread(target=self.session_worker, args=(self.engine, self.audio_q, self.target,
                                                           dict(self.cfg)), name="Session", daemon=True).start()

    def on_audio(self, q, sr, data):
        x = data[:, 0].copy()
        q.put((sr, x))
        self.overlay.level = float(np.sqrt(np.mean(x * x)))  # drives the live sound bars

    def stop_recording(self):
        if not self.recording:
            return
        self.recording = False
        self.busy = True
        self.busy_since = time.time()
        if self.stream:
            try:
                time.sleep(0.12)  # catch the last syllable
                self.stream.stop(); self.stream.close()
            except Exception:
                log.exception("stream close")
            self.stream = None
        if time.time() - self.started_at < 0.3:
            self.audio_q.put("cancel")
        else:
            self.audio_q.put(None)
            if self.cfg["sounds"]: play("stop")
        self.overlay.show("লিখছি…", "#f59e0b")
        self.set_tray_state("busy")

    def session_worker(self, engine, q, target, cfg):
        """Owns the recognizer stream for one dictation, so nothing races with the UI thread."""
        try:
            session = engine.session()
            last_partial = 0.0
            while True:
                item = q.get()
                if item is None:
                    break
                if item == "cancel":
                    self.ui.put(("result", ("", None))); return
                session.feed(*item)
                if time.time() - last_partial > 0.25:
                    p = session.partial()
                    if p:
                        self.ui.put(("partial", p))
                    last_partial = time.time()
            text = clean_text(session.finish())
            try:
                text = apply_word_fixes(text, cfg.get("word_fixes", ""))
            except re.error:
                log.exception("word fixes")
            log.info("transcribed %d chars", len(text))
            if text:
                insert_text(text + (" " if cfg["trailing_space"] else ""), target, cfg["output"],
                            cfg["restore_clipboard"])
            self.ui.put(("result", (text, None)))
        except Exception as exc:
            log.exception("session")
            self.ui.put(("result", ("", str(exc))))

    # ---------------------------------------------------------------- tray
    def create_tray(self):
        import pystray
        from pystray import MenuItem as Item, Menu

        def on(fn):
            return lambda icon, item: self.ui.put(("tray", fn))

        def set_engine(name):
            return on(lambda: self.change_engine(name))

        menu = Menu(
            Item("Open Kothok", on(self.show_window), default=True),
            Item(lambda i: "■  Stop dictation" if self.recording else "●  Start dictation",
                 on(lambda: self.stop_recording() if self.recording else self.start_recording())),
            Item("Copy last dictation", on(self.copy_last), enabled=lambda i: bool(self.history)),
            Menu.SEPARATOR,
            Item("Engine", Menu(
                Item("Bangla + English", set_engine("mixed"),
                     checked=lambda i: self.cfg["engine"] == "mixed", radio=True),
                Item("Bangla only (fast)", set_engine("bangla"),
                     checked=lambda i: self.cfg["engine"] == "bangla", radio=True),
            )),
            Item("Mode", Menu(
                Item("Hold to talk", on(lambda: self.set_mode("hold")),
                     checked=lambda i: self.cfg["mode"] == "hold", radio=True),
                Item("Press to start / stop", on(lambda: self.set_mode("toggle")),
                     checked=lambda i: self.cfg["mode"] == "toggle", radio=True),
            )),
            Item("Pause shortcut", on(self.toggle_pause), checked=lambda i: self.paused),
            Item("Sound feedback", on(self.toggle_sounds), checked=lambda i: self.cfg["sounds"]),
            Item("Start with Windows", on(self.toggle_autostart), checked=lambda i: self.cfg["autostart"]),
            Item("Popup position", Menu(*[
                Item(label, on(lambda p=p: self.set_position(p)),
                     checked=lambda i, p=p: self.cfg.get("popup_position", "bottom-center") == p, radio=True)
                for p, label in POSITIONS.items()])),
            Item("Theme", Menu(*[
                Item(label, on(lambda t=t: self.set_theme(t)),
                     checked=lambda i, t=t: self.cfg.get("theme", "light") == t, radio=True)
                for t, label in THEMES.items()])),
            Item("Auto update", on(self.toggle_auto_update), checked=lambda i: self.cfg.get("auto_update", True),
                 enabled=lambda i: Updater.supported()),
            Menu.SEPARATOR,
            Item("Open log file", on(lambda: os.startfile(str(LOG_FILE)) if LOG_FILE.exists() else None)),
            Item("About / rotexit.com", on(lambda: os.startfile(WEBSITE))),
            Item("Exit", on(self.quit)),
        )
        self.icons = {s: make_icon(s) for s in ("idle", "rec", "busy", "error")}
        self.tray = pystray.Icon(APP_ID, self.icons["busy"], f"{APP_NAME} - loading", menu)
        self.tray.run_detached()

    def set_tray_state(self, state, tip=None):
        if self.tray:
            try:
                self.tray.icon = self.icons[state]
                if tip:
                    self.tray.title = (APP_NAME + " - " + tip)[:127]
            except Exception:
                log.exception("tray update")

    def notify(self, msg):
        try:
            self.tray.notify(msg, APP_NAME)
        except Exception:
            pass

    def set_mode(self, mode):
        self.cfg["mode"] = mode; self.persist()
        self.mode_var.set({v: k for k, v in self.mode_map.items()}[mode]); self.refresh_ready()

    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused and self.recording:
            self.stop_recording()
        self.refresh_ready()
        self.notify("Shortcut paused" if self.paused else f"Shortcut active - {self.hotkey_hint()}")

    def install_update_when_idle(self):
        """Restart into the new version only when nobody is dictating (idle for 2+ minutes)."""
        if not self.updater.ready or not self.cfg.get("auto_update", True):
            return
        if self.recording or self.busy or time.time() - self.last_used < 120:
            self.root.after(60_000, self.install_update_when_idle)
            return
        try:
            self.updater.apply()
        except Exception:
            log.exception("update apply failed")
            return
        self.quit()

    def set_position(self, pos):
        self.cfg["popup_position"] = pos; self.persist()
        self.overlay.place(pos)
        if hasattr(self, "pos_var"):
            self.pos_var.set(POSITIONS[pos])
        if not self.recording and not self.busy:  # quick preview of the new spot
            self.overlay.show("এখানে দেখাবে", "#22c55e"); self.root.after(1500, self.overlay.hide)

    def set_theme(self, theme):
        import customtkinter as ctk
        self.cfg["theme"] = theme; self.persist()
        ctk.set_appearance_mode(theme)
        if hasattr(self, "theme_var"):
            self.theme_var.set(THEMES[theme])

    def toggle_auto_update(self):
        self.cfg["auto_update"] = not self.cfg.get("auto_update", True); self.persist()

    def toggle_sounds(self):
        self.cfg["sounds"] = not self.cfg["sounds"]; self.persist(); self.sounds_var.set(self.cfg["sounds"])

    def toggle_autostart(self):
        self.cfg["autostart"] = not self.cfg["autostart"]
        try:
            set_autostart(self.cfg["autostart"])
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Could not change startup setting:\n{exc}")
        self.persist(); self.autostart_var.set(self.cfg["autostart"])

    def change_engine(self, name):
        if name == self.cfg["engine"] and self.engine:
            return
        if not engine_available(name):
            messagebox.showwarning(APP_NAME, f"Model for '{ENGINE_LABELS[name]}' is not installed.\n"
                                             f"Put it in: {MODELS}")
            return
        self.cfg["engine"] = name; self.persist()
        self.engine_var.set({v: k for k, v in self.engine_map.items()}[name])
        self.load_engine_async()

    # ---------------------------------------------------------------- window
    def build_window(self):
        import customtkinter as ctk
        r = self.root
        r.title(f"{APP_NAME}")
        r.geometry("860x660"); r.minsize(820, 620)  # was 700x930 (single column)
        # customtkinter replaces the window icon ~200ms after start, so set ours after that
        # (frozen builds keep bundled data in sys._MEIPASS = the _internal folder)
        ico = Path(getattr(sys, "_MEIPASS", ROOT)) / "app.ico"

        def apply_icon():
            try:
                if ico.exists():
                    r.iconbitmap(default=str(ico))
                    r.iconbitmap(str(ico))
            except Exception:
                log.exception("icon")
        apply_icon(); r.after(300, apply_icon)
        r.configure(fg_color=C_BG)
        F = lambda size, weight="normal": ctk.CTkFont(family="Segoe UI", size=size, weight=weight)
        BN = lambda size, weight="normal": ctk.CTkFont(family="Nirmala UI", size=size, weight=weight)

        # Compact two-column layout (v2.6). The previous single-column layout (one card per row,
        # 700x930) is kept below in _build_window_v1_reference for reference.
        outer = ctk.CTkFrame(r, fg_color=C_BG, corner_radius=0)
        outer.pack(fill="both", expand=True)
        outer.grid_columnconfigure((0, 1), weight=1, uniform="col")

        # ---- header
        head = ctk.CTkFrame(outer, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(16, 6))
        head.grid_columnconfigure(1, weight=1)
        try:
            self._logo = ctk.CTkImage(make_icon("idle", 128), size=(44, 44))
            ctk.CTkLabel(head, image=self._logo, text="").grid(row=0, column=0, rowspan=2, padx=(0, 12))
        except Exception:
            pass
        ctk.CTkLabel(head, text=f"{APP_BN}  Kothok", font=BN(22, "bold"), text_color=C_TEXT).grid(row=0, column=1, sticky="sw")
        ctk.CTkLabel(head, text="Offline dictation • Bangla + English • anywhere on Windows",
                     font=F(12), text_color=C_MUTED).grid(row=1, column=1, sticky="nw")
        self.chip = ctk.CTkLabel(head, text="  Loading…  ", font=F(12, "bold"), corner_radius=12,
                                 fg_color=C_AMBER, text_color="#1a1a1a", height=26)
        self.chip.grid(row=0, column=2, rowspan=2, sticky="e")

        def card(row, col, title, subtitle=None, span=1):
            c = ctk.CTkFrame(outer, fg_color=C_CARD, corner_radius=12, border_width=1, border_color=C_BORDER)
            c.grid(row=row, column=col, columnspan=span, sticky="nsew",
                   padx=(20 if col == 0 else 6, 20 if col + span == 2 else 6), pady=6)
            c.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(c, text=title, font=F(13, "bold"), text_color=C_TEXT).grid(
                row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(12, 0 if subtitle else 6))
            if subtitle:
                ctk.CTkLabel(c, text=subtitle, font=F(11), text_color=C_MUTED, justify="left").grid(
                    row=1, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 6))
            return c

        def label(c, row, text, pady=5):
            ctk.CTkLabel(c, text=text, font=F(12), text_color=C_MUTED, width=82, anchor="w").grid(
                row=row, column=0, sticky="w", padx=(16, 6), pady=pady)

        def segmented(c, row, values, var, command, last=False):
            ctk.CTkSegmentedButton(c, values=values, variable=var, font=F(12),
                                   selected_color=C_SEL, selected_hover_color=C_SEL_H, text_color=C_TEXT,
                                   unselected_color=C_KEY, fg_color=C_KEY, command=command).grid(
                row=row, column=1, columnspan=2, sticky="w", padx=(0, 16), pady=(5, 14 if last else 5))

        save = lambda _v=None: self.save_settings(quiet=True)

        # ---- shortcut (left)
        c = card(1, 0, "Shortcut", "Cursor রেখে shortcut চেপে কথা বলুন।")
        self.hotkey_var = tk.StringVar(value=self.cfg["hotkey"])
        self.hotkey_lbl = ctk.CTkLabel(c, textvariable=self.hotkey_var, font=ctk.CTkFont("Consolas", 18, "bold"),
                                       fg_color=C_KEY, corner_radius=10, text_color=C_TEXT, height=38, width=150)
        self.hotkey_lbl.grid(row=2, column=0, columnspan=2, sticky="w", padx=16, pady=(2, 4))
        self.capture_btn = ctk.CTkButton(c, text="Change shortcut", command=self.begin_capture, width=140,
                                         height=34, fg_color=C_ACCENT, hover_color=C_ACCENT_H, font=F(12, "bold"))
        self.capture_btn.grid(row=2, column=2, sticky="e", padx=16)
        label(c, 3, "Mode")
        self.mode_map = {"Hold to talk": "hold", "Press to start / stop": "toggle"}
        self.mode_var = tk.StringVar(value={v: k for k, v in self.mode_map.items()}[self.cfg["mode"]])
        segmented(c, 3, list(self.mode_map), self.mode_var, save, last=True)

        # ---- recognition (right)
        c = card(1, 1, "Recognition", "সব কিছু আপনার PC-তেই চলে — internet লাগে না।")
        label(c, 2, "Engine")
        self.engine_map = {"Bangla + English": "mixed", "Bangla only (fast)": "bangla"}
        self.engine_var = tk.StringVar(value={v: k for k, v in self.engine_map.items()}[self.cfg["engine"]])
        segmented(c, 2, list(self.engine_map), self.engine_var, save)
        self.lang_var = tk.StringVar(value=LANG_LABELS.get(self.cfg["language"], LANG_LABELS["auto"]))
        # (Language picker stays disabled - see _build_window_v1_reference)
        label(c, 3, "Microphone")
        self.mics = self.list_mics()
        self.mic_var = tk.StringVar(value=self.cfg["device"] or "System default")
        ctk.CTkOptionMenu(c, values=["System default"] + self.mics, variable=self.mic_var, font=F(12),
                          fg_color=C_KEY, button_color=C_KEY, button_hover_color=C_BORDER, width=250, text_color=C_TEXT,
                          dropdown_fg_color=C_CARD, dropdown_text_color=C_TEXT, dropdown_hover_color=C_KEY,
                          dynamic_resizing=False, command=save).grid(
            row=3, column=1, columnspan=2, sticky="w", padx=(0, 16), pady=(5, 14))

        # ---- settings (full width: choices left, switches right)
        c = card(2, 0, "Settings", span=2)
        c.grid_columnconfigure(1, weight=0)
        c.grid_columnconfigure(3, weight=1)
        label(c, 1, "Insert by")
        self.output_map = {"Paste (recommended)": "paste", "Type characters": "type"}
        self.output_var = tk.StringVar(value={v: k for k, v in self.output_map.items()}[self.cfg["output"]])
        segmented(c, 1, list(self.output_map), self.output_var, save)
        label(c, 2, "Theme")
        self.theme_var = tk.StringVar(value=THEMES[self.cfg.get("theme", "light")])
        segmented(c, 2, list(THEMES.values()), self.theme_var,
                  lambda v: self.set_theme({b: a for a, b in THEMES.items()}[v]))
        label(c, 3, "Popup")
        self.pos_var = tk.StringVar(value=POSITIONS[self.cfg.get("popup_position", "bottom-center")])
        segmented(c, 3, list(POSITIONS.values()), self.pos_var,
                  lambda v: self.set_position({b: a for a, b in POSITIONS.items()}[v]), last=True)
        sw = ctk.CTkFrame(c, fg_color="transparent")
        sw.grid(row=1, column=3, rowspan=3, sticky="ne", padx=(10, 16), pady=(4, 12))
        self.restore_var = tk.BooleanVar(value=self.cfg["restore_clipboard"])
        self.space_var = tk.BooleanVar(value=self.cfg["trailing_space"])
        self.sounds_var = tk.BooleanVar(value=self.cfg["sounds"])
        self.autostart_var = tk.BooleanVar(value=self.cfg["autostart"])
        for i, (text, var) in enumerate((("Restore clipboard after paste", self.restore_var),
                                         ("Add a space after text", self.space_var),
                                         ("Sound feedback", self.sounds_var),
                                         ("Start with Windows", self.autostart_var))):
            ctk.CTkSwitch(sw, text=text, variable=var, font=F(12), progress_color=C_ACCENT, text_color=C_TEXT,
                          command=save).grid(row=i, column=0, sticky="w", pady=4)

        # ---- recent dictations (full width, compact)
        c = card(3, 0, "Recent dictations", span=2)
        c.grid_rowconfigure(1, weight=1)
        outer.grid_rowconfigure(3, weight=1)
        bf = ctk.CTkFrame(c, fg_color="transparent")
        bf.grid(row=0, column=2, sticky="e", padx=16, pady=(10, 4))
        ctk.CTkButton(bf, text="Word fixes", width=100, height=28, command=self.edit_word_fixes, fg_color=C_ACCENT,
                      hover_color=C_ACCENT_H, font=F(12, "bold")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bf, text="Copy last", width=90, height=28, command=self.copy_last, fg_color=C_KEY,
                      text_color=C_TEXT, hover_color=C_BORDER, font=F(12)).pack(side="left")
        ctk.CTkButton(bf, text="Clear", width=70, height=28, command=lambda: self.text.delete("1.0", "end"),
                      fg_color=C_KEY, hover_color=C_BORDER, text_color=C_TEXT, font=F(12)).pack(side="left", padx=(8, 0))
        self.text = ctk.CTkTextbox(c, height=56, font=BN(14), fg_color=C_KEY, text_color=C_TEXT,
                                   border_width=0, corner_radius=10, wrap="word")
        self.text.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=16, pady=(0, 14))

        # ---- footer
        foot = ctk.CTkFrame(outer, fg_color="transparent")
        foot.grid(row=4, column=0, columnspan=2, sticky="ew", padx=20, pady=(2, 14))
        self.status_var = tk.StringVar(value="Starting…")
        ctk.CTkLabel(foot, textvariable=self.status_var, font=F(11), text_color=C_MUTED).pack(side="left")
        link = ctk.CTkLabel(foot, text=f"v{VERSION}  •  Developed by rotexit.com", font=F(11, "bold"),
                            text_color=C_ACCENT, cursor="hand2")
        ctk.CTkButton(foot, text="Minimise to tray", width=140, height=30, command=self.hide_window,
                      fg_color=C_ACCENT, hover_color=C_ACCENT_H, font=F(12, "bold")).pack(side="right", padx=(12, 0))
        link.pack(side="right")
        link.bind("<Button-1>", lambda e: os.startfile(WEBSITE))

    def _build_window_v1_reference(self):  # pragma: no cover - old layout, not called
        """Previous single-column settings layout, kept for reference."""
        return
        # outer = ctk.CTkFrame(r, fg_color=C_BG, corner_radius=0)
        # outer.pack(fill="both", expand=True)
        # outer.grid_columnconfigure(0, weight=1)

        # # ---- header
        # head = ctk.CTkFrame(outer, fg_color="transparent"); head.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 6))
        # head.grid_columnconfigure(1, weight=1)
        # try:
        #     self._logo = ctk.CTkImage(make_icon("idle", 128), size=(52, 52))
        #     ctk.CTkLabel(head, image=self._logo, text="").grid(row=0, column=0, rowspan=2, padx=(0, 14))
        # except Exception:
        #     pass
        # ctk.CTkLabel(head, text=f"{APP_BN}  Kothok", font=BN(26, "bold"), text_color=C_TEXT).grid(row=0, column=1, sticky="sw")
        # ctk.CTkLabel(head, text="Offline dictation • Bangla + English • anywhere on Windows",
        #              font=F(12), text_color=C_MUTED).grid(row=1, column=1, sticky="nw")
        # self.chip = ctk.CTkLabel(head, text="  Loading…  ", font=F(12, "bold"), corner_radius=12,
        #                          fg_color=C_AMBER, text_color="#1a1a1a", height=26)
        # self.chip.grid(row=0, column=2, rowspan=2, sticky="e")

        # def card(row, title, subtitle=None):
        #     c = ctk.CTkFrame(outer, fg_color=C_CARD, corner_radius=14, border_width=1, border_color=C_BORDER)
        #     c.grid(row=row, column=0, sticky="ew", padx=24, pady=6)
        #     c.grid_columnconfigure(1, weight=1)
        #     ctk.CTkLabel(c, text=title, font=F(14, "bold"), text_color=C_TEXT).grid(
        #         row=0, column=0, columnspan=3, sticky="w", padx=18, pady=(14, 0 if subtitle else 8))
        #     if subtitle:
        #         ctk.CTkLabel(c, text=subtitle, font=F(11), text_color=C_MUTED, justify="left").grid(
        #             row=1, column=0, columnspan=3, sticky="w", padx=18, pady=(0, 8))
        #     return c

        # def label(c, row, text):
        #     ctk.CTkLabel(c, text=text, font=F(12), text_color=C_MUTED, width=110, anchor="w").grid(
        #         row=row, column=0, sticky="w", padx=(18, 8), pady=6)

        # # ---- shortcut card
        # c = card(1, "Shortcut", "কার্সর যেখানে রাখবেন, shortcut চেপে কথা বলুন — লেখা সেখানেই বসে যাবে।")
        # self.hotkey_var = tk.StringVar(value=self.cfg["hotkey"])
        # self.hotkey_lbl = ctk.CTkLabel(c, textvariable=self.hotkey_var, font=ctk.CTkFont("Consolas", 20, "bold"),
        #                                fg_color=C_KEY, corner_radius=10, text_color=C_TEXT, height=44, width=220)
        # self.hotkey_lbl.grid(row=2, column=0, columnspan=2, sticky="w", padx=18, pady=(2, 8))
        # self.capture_btn = ctk.CTkButton(c, text="Change shortcut", command=self.begin_capture, width=150,
        #                                  height=36, fg_color=C_ACCENT, hover_color=C_ACCENT_H, font=F(12, "bold"))
        # self.capture_btn.grid(row=2, column=2, sticky="e", padx=18)
        # label(c, 3, "Mode")
        # self.mode_map = {"Hold to talk": "hold", "Press to start / stop": "toggle"}
        # self.mode_var = tk.StringVar(value={v: k for k, v in self.mode_map.items()}[self.cfg["mode"]])
        # ctk.CTkSegmentedButton(c, values=list(self.mode_map), variable=self.mode_var, font=F(12),
        #                        selected_color=C_SEL, selected_hover_color=C_SEL_H, text_color=C_TEXT, unselected_color=C_KEY, fg_color=C_KEY,
        #                        command=lambda _v: self.save_settings(quiet=True)).grid(
        #     row=3, column=1, columnspan=2, sticky="w", padx=(0, 18), pady=(6, 16))

        # # ---- recognition card
        # c = card(2, "Recognition", "সব কিছু আপনার PC-তেই চলে — internet বা cloud লাগে না।")
        # label(c, 2, "Engine")
        # self.engine_map = {"Bangla + English": "mixed", "Bangla only (fast)": "bangla"}
        # self.engine_var = tk.StringVar(value={v: k for k, v in self.engine_map.items()}[self.cfg["engine"]])
        # ctk.CTkSegmentedButton(c, values=list(self.engine_map), variable=self.engine_var, font=F(12),
        #                        selected_color=C_SEL, selected_hover_color=C_SEL_H, text_color=C_TEXT, unselected_color=C_KEY, fg_color=C_KEY,
        #                        command=lambda _v: self.save_settings(quiet=True)).grid(
        #     row=2, column=1, columnspan=2, sticky="w", padx=(0, 18), pady=6)
        # self.lang_var = tk.StringVar(value=LANG_LABELS.get(self.cfg["language"], LANG_LABELS["auto"]))
        # # Language picker disabled: it only applied to the old turbo engine; "Bangla + English" now
        # # detects English phrases automatically.
        # # label(c, 3, "Language")
        # # ctk.CTkOptionMenu(c, values=list(LANG_LABELS.values()), variable=self.lang_var, font=F(12),
        # #                   fg_color=C_KEY, button_color=C_KEY, button_hover_color=C_BORDER, width=260,
        # #                   command=lambda _v: self.save_settings(quiet=True)).grid(
        # #     row=3, column=1, columnspan=2, sticky="w", pady=6)
        # label(c, 4, "Microphone")
        # self.mics = self.list_mics()
        # self.mic_var = tk.StringVar(value=self.cfg["device"] or "System default")
        # ctk.CTkOptionMenu(c, values=["System default"] + self.mics, variable=self.mic_var, font=F(12),
        #                   fg_color=C_KEY, button_color=C_KEY, button_hover_color=C_BORDER, width=380, text_color=C_TEXT,
        #                   dropdown_fg_color=C_CARD, dropdown_text_color=C_TEXT, dropdown_hover_color=C_KEY,
        #                   dynamic_resizing=False, command=lambda _v: self.save_settings(quiet=True)).grid(
        #     row=4, column=1, columnspan=2, sticky="w", pady=(6, 16))

        # # ---- behaviour card
        # c = card(3, "Behaviour")
        # label(c, 1, "Insert by")
        # self.output_map = {"Paste (recommended)": "paste", "Type characters": "type"}
        # self.output_var = tk.StringVar(value={v: k for k, v in self.output_map.items()}[self.cfg["output"]])
        # ctk.CTkSegmentedButton(c, values=list(self.output_map), variable=self.output_var, font=F(12),
        #                        selected_color=C_SEL, selected_hover_color=C_SEL_H, text_color=C_TEXT, unselected_color=C_KEY, fg_color=C_KEY,
        #                        command=lambda _v: self.save_settings(quiet=True)).grid(
        #     row=1, column=1, columnspan=2, sticky="w", pady=6)
        # sw = ctk.CTkFrame(c, fg_color="transparent"); sw.grid(row=2, column=0, columnspan=3, sticky="ew", padx=18, pady=(4, 14))
        # sw.grid_columnconfigure((0, 1), weight=1)
        # self.restore_var = tk.BooleanVar(value=self.cfg["restore_clipboard"])
        # self.space_var = tk.BooleanVar(value=self.cfg["trailing_space"])
        # self.sounds_var = tk.BooleanVar(value=self.cfg["sounds"])
        # self.autostart_var = tk.BooleanVar(value=self.cfg["autostart"])
        # for i, (text, var) in enumerate((("Restore clipboard after paste", self.restore_var),
        #                                  ("Add a space after text", self.space_var),
        #                                  ("Sound feedback", self.sounds_var),
        #                                  ("Start with Windows", self.autostart_var))):
        #     ctk.CTkSwitch(sw, text=text, variable=var, font=F(12), progress_color=C_ACCENT, text_color=C_TEXT,
        #                   command=lambda: self.save_settings(quiet=True)).grid(
        #         row=i // 2, column=i % 2, sticky="w", pady=5)
        # label(c, 3, "Theme")
        # self.theme_var = tk.StringVar(value=THEMES[self.cfg.get("theme", "light")])
        # ctk.CTkSegmentedButton(c, values=list(THEMES.values()), variable=self.theme_var, font=F(12),
        #                        selected_color=C_SEL, selected_hover_color=C_SEL_H, text_color=C_TEXT, unselected_color=C_KEY, fg_color=C_KEY,
        #                        command=lambda v: self.set_theme({b: a for a, b in THEMES.items()}[v])).grid(
        #     row=3, column=1, columnspan=2, sticky="w", pady=(0, 8))
        # label(c, 4, "Popup")
        # self.pos_var = tk.StringVar(value=POSITIONS[self.cfg.get("popup_position", "bottom-center")])
        # ctk.CTkSegmentedButton(c, values=list(POSITIONS.values()), variable=self.pos_var, font=F(12),
        #                        selected_color=C_SEL, selected_hover_color=C_SEL_H, text_color=C_TEXT, unselected_color=C_KEY, fg_color=C_KEY,
        #                        command=lambda v: self.set_position({b: a for a, b in POSITIONS.items()}[v])).grid(
        #     row=4, column=1, columnspan=2, sticky="w", pady=(0, 14))

        # # ---- history card
        # c = card(4, "Recent dictations", "এখানে click করে shortcut চেপে test করতে পারেন।")
        # c.grid_rowconfigure(2, weight=1)
        # c.grid_configure(sticky="nsew"); outer.grid_rowconfigure(4, weight=1)
        # self.text = ctk.CTkTextbox(c, height=70, font=BN(15), fg_color=C_KEY, text_color=C_TEXT,
        #                            border_width=0, corner_radius=10, wrap="word")
        # self.text.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=18, pady=(0, 10))
        # bf = ctk.CTkFrame(c, fg_color="transparent"); bf.grid(row=3, column=0, columnspan=3, sticky="ew", padx=18, pady=(0, 14))
        # ctk.CTkButton(bf, text="Copy last", width=110, command=self.copy_last, fg_color=C_KEY, text_color=C_TEXT,
        #               hover_color=C_BORDER, font=F(12)).pack(side="left")
        # ctk.CTkButton(bf, text="Clear", width=80, command=lambda: self.text.delete("1.0", "end"),
        #               fg_color=C_KEY, hover_color=C_BORDER, text_color=C_TEXT, font=F(12)).pack(side="left", padx=8)
        # ctk.CTkButton(bf, text="Minimise to tray", width=150, command=self.hide_window, fg_color=C_ACCENT,
        #               hover_color=C_ACCENT_H, font=F(12, "bold")).pack(side="right")


    def list_mics(self):
        try:
            import sounddevice as sd
            default_api = sd.default.hostapi if isinstance(sd.default.hostapi, int) else 0
            names = []
            for d in sd.query_devices():
                if d["max_input_channels"] > 0 and d["hostapi"] == default_api and d["name"] not in names:
                    names.append(d["name"])
            return names
        except Exception:
            log.exception("list mics")
            return []

    def begin_capture(self):
        self.hotkey_var.set("Press keys…")
        self.capture_btn.configure(state="disabled", text="Esc = cancel")
        self.hook.capture = True

    def on_captured(self, combo):
        self.capture_btn.configure(state="normal", text="Change shortcut")
        if combo:
            try:
                self.hook.set_hotkey(combo)
                self.cfg["hotkey"] = combo; self.persist()
            except ValueError as exc:
                messagebox.showerror(APP_NAME, str(exc))
        self.hotkey_var.set(self.cfg["hotkey"])
        self.refresh_ready()

    def save_settings(self, quiet=False):
        engine = self.engine_map[self.engine_var.get()]
        language = {v: k for k, v in LANG_LABELS.items()}[self.lang_var.get()]
        mic = self.mic_var.get()
        if not engine_available(engine):
            messagebox.showwarning(APP_NAME, f"That model is not installed.\nPut it in: {MODELS}")
            self.engine_var.set({v: k for k, v in self.engine_map.items()}[self.cfg["engine"]])
            return
        reload_needed = engine != self.cfg["engine"]
        if self.autostart_var.get() != self.cfg["autostart"]:
            try:
                set_autostart(self.autostart_var.get())
            except OSError as exc:
                messagebox.showerror(APP_NAME, f"Could not change startup setting:\n{exc}")
        self.cfg.update(engine=engine, language=language, device="" if mic == "System default" else mic,
                        mode=self.mode_map[self.mode_var.get()], output=self.output_map[self.output_var.get()],
                        restore_clipboard=self.restore_var.get(), trailing_space=self.space_var.get(),
                        sounds=self.sounds_var.get(), autostart=self.autostart_var.get())
        self.persist()
        if reload_needed or not self.engine:
            self.load_engine_async()
        else:
            self.refresh_ready()

    def edit_word_fixes(self):
        """Small editor for the user's own corrections (names, brands, words the model keeps mishearing)."""
        w = ctk.CTkToplevel(self.root)
        w.title("Word fixes"); w.geometry("460x420"); w.transient(self.root); w.grab_set()
        ctk.CTkLabel(w, text="ভুল শব্দ = সঠিক শব্দ   (প্রতি লাইনে একটা)", font=BN(14, "bold"),
                     text_color=C_TEXT).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(w, text="Example:  কতক = কথক     rotex it = rotexit\nEvery dictation is corrected with this list.",
                     font=F(11), text_color=C_MUTED, justify="left").pack(anchor="w", padx=16)
        box = ctk.CTkTextbox(w, font=BN(14), fg_color=C_KEY, text_color=C_TEXT, corner_radius=10)
        box.pack(fill="both", expand=True, padx=16, pady=10)
        box.insert("1.0", self.cfg.get("word_fixes", ""))

        def done():
            self.cfg["word_fixes"] = box.get("1.0", "end").strip()
            self.persist(); w.destroy()
        ctk.CTkButton(w, text="Save", command=done, fg_color=C_ACCENT, hover_color=C_ACCENT_H,
                      font=F(12, "bold")).pack(anchor="e", padx=16, pady=(0, 14))

    def refresh_ready(self):
        if self.engine:
            self.set_status(f"Ready — {self.hotkey_hint()}", "idle")

    def persist(self):
        try:
            save_config(self.cfg)
        except OSError:
            log.exception("save config")

    def add_history(self, text):
        self.history.append(text)
        self.text.insert("end", text + "\n")
        self.text.see("end")

    def copy_last(self):
        if self.history:
            clipboard_set(self.history[-1])

    def set_status(self, msg, state=None):
        if hasattr(self, "status_var"):
            self.status_var.set(msg)
        if state and hasattr(self, "chip"):
            text, colour = {"idle": ("Ready", C_GREEN), "rec": ("Listening", C_RED),
                            "busy": ("Working", C_AMBER), "error": ("Problem", C_GREY)}[state]
            if state == "idle" and self.paused:
                text, colour = "Paused", C_GREY
            self.chip.configure(text=f"  ●  {text}  ", fg_color=colour)
        if state:
            self.set_tray_state(state, msg)

    def show_window(self):
        self.root.deiconify(); self.root.lift(); self.root.focus_force()
        if not getattr(self, "_centred", False):
            self._centred = True
            self.root.after(60, self.centre_window)

    def centre_window(self):
        """Centre the window in the work area (screen minus taskbar), using real pixel sizes."""
        try:
            self.root.update_idletasks()
            hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            win, wa = wintypes.RECT(), wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(win))
            user32.SystemParametersInfoW(0x30, 0, ctypes.byref(wa), 0)  # SPI_GETWORKAREA
            w, h = win.right - win.left, win.bottom - win.top
            x = wa.left + max(0, (wa.right - wa.left - w) // 2)
            y = wa.top + max(0, (wa.bottom - wa.top - h) // 2)
            user32.SetWindowPos(hwnd, None, x, y, 0, 0, 0x1 | 0x4 | 0x10)  # NOSIZE | NOZORDER | NOACTIVATE
        except Exception:
            log.exception("centre window")

    def hide_window(self):
        self.root.withdraw()
        if not self.tray_hint_shown:
            self.tray_hint_shown = True
            self.notify(f"কথক background-এ চালু আছে। {self.talk_hint_bn()}। "
                        "আবার খুলতে ঘড়ির পাশের icon-এ ক্লিক করুন।")

    def quit(self):
        if self.recording:
            self.stop_recording()
        self.hook.stop()
        if self.tray:
            self.tray.stop()
        self.root.after(50, self.root.destroy)


def splash_text(text):
    """Status line on the startup banner (frozen build only - see Kothok.spec)."""
    try:
        import pyi_splash
        pyi_splash.update_text(text)
    except Exception:
        pass


def close_splash():
    try:
        import pyi_splash
        pyi_splash.close()
    except Exception:
        pass


kernel32.CreateEventW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
kernel32.CreateEventW.restype = wintypes.HANDLE
kernel32.SetEvent.argtypes = (wintypes.HANDLE,)
kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
SHOW_EVENT = f"Local\\{APP_ID}_ShowWindow"


def single_instance():
    handle = kernel32.CreateMutexW(None, False, f"Local\\{APP_ID}_SingleInstance")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        # Already running: ask that copy to bring its window to the front (was only an "already running" box)
        close_splash()
        if "--tray" not in sys.argv:
            ev = kernel32.CreateEventW(None, False, False, SHOW_EVENT)
            if not (ev and kernel32.SetEvent(ev)):
                user32.MessageBoxW(None, f"{APP_NAME} is already running.\nLook for the microphone icon in the system tray.",
                                   APP_NAME, 0x40)
        sys.exit(0)
    return handle


def watch_show_requests(app):
    """A second launch of Kothok.exe signals SHOW_EVENT -> open this (running) copy's window."""
    ev = kernel32.CreateEventW(None, False, False, SHOW_EVENT)
    while ev:
        if kernel32.WaitForSingleObject(ev, 0xFFFFFFFF) == 0:
            app.ui.put(("tray", app.show_window))


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    try:  # own taskbar identity, so Windows shows the Kothok icon instead of python/tk
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)  # was "rotexit.Kothok" - shown as the toast heading
    except Exception:
        pass
    try:  # name + icon for notifications (otherwise Windows shows "rotexit.Kothok" with no icon)
        ico = Path(getattr(sys, "_MEIPASS", ROOT)) / "app.ico"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\Classes\\AppUserModelId\\" + APP_ID) as k:
            winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
            if ico.exists():
                winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, str(ico))
    except OSError:
        pass
    globals()["_MUTEX"] = single_instance()  # must stay alive for the process lifetime
    log.info("starting %s %s from %s", APP_NAME, VERSION, ROOT)
    splash_text("Starting…")
    import customtkinter as ctk
    # ctk.set_appearance_mode("dark")  # was dark only; now Light (default) / Dark / System
    theme = load_config().get("theme", "light")
    ctk.set_appearance_mode(theme if theme in THEMES else "light")
    root = ctk.CTk()
    root.report_callback_exception = lambda *a: log.error("tk error:\n%s", "".join(traceback.format_exception(*a)))
    splash_text("Opening window…")
    app = App(root)
    threading.Thread(target=watch_show_requests, args=(app,), name="ShowRequests", daemon=True).start()
    root.after(400, close_splash)  # window is drawn by now; models keep loading ("Loading…" chip)
    root.mainloop()
    log.info("exit")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("fatal")
        close_splash()
        user32.MessageBoxW(None, f"Unexpected error - see log:\n{LOG_FILE}\n\n{traceback.format_exc()[-600:]}",
                           APP_NAME, 0x10)
        raise
