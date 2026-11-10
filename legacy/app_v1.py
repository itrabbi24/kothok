"""Portable, tray-based Bengali push-to-talk dictation for Windows."""
import ctypes
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

import numpy as np
import pystray
import sounddevice as sd
import sherpa_onnx
from PIL import Image, ImageDraw

ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
MODEL = ROOT / "models" / "bn"
USER32 = ctypes.windll.user32
VK = {**{chr(i): i for i in range(65, 91)}, **{str(i): 0x30 + i for i in range(10)}, **{f"F{i}": 0x6F + i for i in range(1, 13)}}
MODIFIER_VK = {"None": 0, "CTRL": 0x11, "ALT": 0x12, "SHIFT": 0x10, "WIN": 0x5B}


def make_recognizer():
    names = ("encoder.onnx", "decoder.onnx", "joiner.onnx", "tokens.txt")
    if not all((MODEL / name).exists() for name in names):
        raise FileNotFoundError("Bengali model is missing. Run download-model.ps1 first.")
    return sherpa_onnx.OnlineRecognizer.from_transducer(
        tokens=str(MODEL / "tokens.txt"), encoder=str(MODEL / "encoder.onnx"),
        decoder=str(MODEL / "decoder.onnx"), joiner=str(MODEL / "joiner.onnx"),
        num_threads=2, sample_rate=16000, feature_dim=80,
        model_type="zipformer2", decoding_method="greedy_search",
    )


def key_code(value):
    key = value.strip().upper()
    if key not in VK: raise ValueError("Use one key: F1-F12, A-Z, or 0-9")
    return VK[key]


def tray_image():
    image = Image.new("RGB", (64, 64), "#1769e0")
    ImageDraw.Draw(image).text((18, 14), "Bn", fill="white")
    return image


class App:
    def __init__(self, root):
        self.root = root; self.running = False; self.stream = None; self.target_hwnd = None; self.session_text = ""
        self.key_down = False; self.tray = None; self.last_committed = ""
        root.title("Bangla Voice to Text - Offline"); root.geometry("780x570")
        root.grid_rowconfigure(3, weight=1); root.grid_columnconfigure(0, weight=1)
        tk.Label(root, text="Bangla Voice to Text", font=("Segoe UI", 22, "bold")).grid(row=0, column=0, pady=(10, 2))
        tk.Label(root, text="Hold the push-to-talk key, speak, then release it to paste.").grid(row=1, column=0)
        bar = tk.Frame(root); bar.grid(row=2, column=0, pady=8)
        tk.Label(bar, text="Hold:").pack(side=tk.LEFT)
        self.modifier = ttk.Combobox(bar, width=8, state="readonly", values=list(MODIFIER_VK)); self.modifier.set("CTRL"); self.modifier.pack(side=tk.LEFT, padx=4)
        tk.Label(bar, text="+").pack(side=tk.LEFT)
        self.key = ttk.Combobox(bar, width=8, state="readonly", values=list(VK)); self.key.set("R"); self.key.pack(side=tk.LEFT, padx=4)
        tk.Button(bar, text="Apply", command=self.apply_key).pack(side=tk.LEFT)
        self.text = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Nirmala UI", 18), height=12)
        self.text.grid(row=3, column=0, sticky="nsew", padx=18, pady=(2, 8))
        controls = tk.Frame(root); controls.grid(row=4, column=0, pady=(0, 4))
        self.button = tk.Button(controls, text="Hold shortcut to dictate", width=22, command=self.toggle_test); self.button.pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Copy", width=10, command=self.copy).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Clear", width=10, command=lambda: self.text.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=5)
        self.status = tk.Label(root, text="Loading model...", anchor="w"); self.status.grid(row=5, column=0, sticky="ew", padx=18, pady=(0, 8))
        try:
            self.recognizer = make_recognizer(); self.status.config(text="Ready - offline; running in tray")
        except Exception as exc:
            self.recognizer = None; self.status.config(text=str(exc))
        self.apply_key(); self.create_tray(); self.root.after(50, self.poll_key); self.root.withdraw()

    def apply_key(self):
        try:
            self.modifier_vk = MODIFIER_VK[self.modifier.get()]; self.vk = key_code(self.key.get())
            label = self.key.get().upper() if not self.modifier_vk else self.modifier.get() + "+" + self.key.get().upper()
            self.status.config(text=f"Ready - hold {label} to dictate")
        except Exception as exc: messagebox.showerror("Push-to-talk key", str(exc))

    def create_tray(self):
        menu = pystray.Menu(pystray.MenuItem("Show settings", lambda: self.root.after(0, self.show)), pystray.MenuItem("Exit", lambda: self.root.after(0, self.close)))
        self.tray = pystray.Icon("BanglaVTT", tray_image(), "Bangla Voice to Text", menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

    def show(self): self.root.deiconify(); self.root.lift(); self.root.focus_force()

    def poll_key(self):
        pressed = bool(USER32.GetAsyncKeyState(self.vk) & 0x8000) and (not self.modifier_vk or bool(USER32.GetAsyncKeyState(self.modifier_vk) & 0x8000))
        if pressed and not self.key_down: self.start_recording()
        elif not pressed and self.key_down: self.stop_recording()
        self.key_down = pressed; self.root.after(30, self.poll_key)

    def audio_callback(self, indata, frames, time_info, status): self.audio_queue.put(indata[:, 0].copy())

    def worker(self):
        while self.running:
            samples = self.audio_queue.get(); self.stream_recognizer.accept_waveform(16000, samples.astype(np.float32))
            while self.recognizer.is_ready(self.stream_recognizer): self.recognizer.decode_stream(self.stream_recognizer)
            result = self.recognizer.get_result(self.stream_recognizer).strip()
            if result and self.recognizer.is_endpoint(self.stream_recognizer):
                self.session_text = (self.session_text + " " + result).strip(); self.last_committed = result
                self.root.after(0, self.preview); self.recognizer.reset(self.stream_recognizer)

    def start_recording(self):
        if not self.recognizer or self.running: return
        self.target_hwnd = USER32.GetForegroundWindow(); self.session_text = ""; self.last_committed = ""; self.audio_queue = queue.Queue(); self.running = True
        label = self.key.get().upper() if not self.modifier_vk else self.modifier.get() + "+" + self.key.get().upper()
        self.stream_recognizer = self.recognizer.create_stream(); self.status.config(text=f"Listening while {label} is held...")
        threading.Thread(target=self.worker, daemon=True).start()
        self.stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32", blocksize=8000, callback=self.audio_callback); self.stream.start()

    def stop_recording(self):
        if not self.running: return
        self.running = False
        if self.stream: self.stream.stop(); self.stream.close(); self.stream = None
        time.sleep(0.15); self.stream_recognizer.input_finished()
        while self.recognizer.is_ready(self.stream_recognizer): self.recognizer.decode_stream(self.stream_recognizer)
        result = self.recognizer.get_result(self.stream_recognizer).strip()
        if result and result != self.last_committed: self.session_text = (self.session_text + " " + result).strip()
        self.preview(); self.paste_to_target()

    def paste_to_target(self):
        self.status.config(text="Pasted to previous app - offline")
        if not self.session_text or not self.target_hwnd: return
        self.root.clipboard_clear(); self.root.clipboard_append(self.session_text); self.root.update(); USER32.SetForegroundWindow(self.target_hwnd); time.sleep(0.12)
        USER32.keybd_event(0x11, 0, 0, 0); USER32.keybd_event(0x56, 0, 0, 0)
        USER32.keybd_event(0x56, 0, 2, 0); USER32.keybd_event(0x11, 0, 2, 0)

    def preview(self): self.text.delete("1.0", tk.END); self.text.insert("1.0", self.session_text)
    def toggle_test(self): self.stop_recording() if self.running else self.start_recording()
    def copy(self): self.root.clipboard_clear(); self.root.clipboard_append(self.text.get("1.0", tk.END).strip())
    def close(self):
        if self.running: self.stop_recording()
        if self.tray: self.tray.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk(); App(root); root.mainloop()
