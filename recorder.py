"""
RecordAI — Voice Recorder for Windows 10
Records audio from a selected microphone and saves to WAV or MP3.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sounddevice as sd
import numpy as np
import wave
import threading
import time
import os
from datetime import datetime

try:
    import lameenc
    HAS_LAME = True
except ImportError:
    HAS_LAME = False


# ── Theme palettes ──────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "bg": "#1e1e2e",
        "fg": "#cdd6f4",
        "accent": "#89b4fa",
        "btn_bg": "#313244",
        "timer": "#f38ba8",
        "status": "#a6e3a1",
        "rec_bg": "#a6e3a1",
        "stop_bg": "#f38ba8",
        "meter_bg": "#313244",
        "meter_low": "#a6e3a1",
        "meter_mid": "#f9e2af",
        "meter_high": "#f38ba8",
        "disabled": "#45475a",
        "muted": "#6c7086",
        "rec_active": "#94e2d5",
        "stop_active": "#fab387",
        "btn_active": "#1e1e2e",
        "canvas_bg": "#313244",
    },
    "light": {
        "bg": "#eff1f5",
        "fg": "#4c4f69",
        "accent": "#1e66f5",
        "btn_bg": "#ccd0da",
        "timer": "#d20f39",
        "status": "#40a02b",
        "rec_bg": "#40a02b",
        "stop_bg": "#d20f39",
        "meter_bg": "#ccd0da",
        "meter_low": "#40a02b",
        "meter_mid": "#df8e1d",
        "meter_high": "#d20f39",
        "disabled": "#bcc0cc",
        "muted": "#9ca0b0",
        "rec_active": "#179299",
        "stop_active": "#fe640b",
        "btn_active": "#eff1f5",
        "canvas_bg": "#ccd0da",
    },
}


class RecordAIApp:
    """Main application class for the voice recorder."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("RecordAI — Voice Recorder")
        self.root.geometry("560x560")
        self.root.resizable(False, False)
        self._center_window()

        # Recording state
        self.is_recording = False
        self.audio_frames: list[np.ndarray] = []
        self.stream = None
        self.record_thread = None
        self.start_time = 0.0
        self.timer_id = None
        self.sample_rate = 44100

        # File state
        self.last_saved_path = ""
        self.format_var = tk.StringVar(value="MP3" if HAS_LAME else "WAV")

        # Theme state
        self.current_theme = "light"
        self.root.configure(bg=THEMES["light"]["bg"])

        # Style
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self._configure_styles()

        self._build_ui()
        self._populate_devices()

        # Handle window close properly
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Styles ──────────────────────────────────────────────────────────
    def _configure_styles(self, theme: str = None):
        if theme is not None:
            self.current_theme = theme
        c = THEMES[self.current_theme]

        self.root.configure(bg=c["bg"])

        self.style.configure("TFrame", background=c["bg"])
        self.style.configure("TLabel", background=c["bg"],
                             foreground=c["fg"], font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", background=c["bg"],
                             foreground=c["accent"],
                             font=("Segoe UI", 18, "bold"))
        self.style.configure("Timer.TLabel", background=c["bg"],
                             foreground=c["timer"],
                             font=("Consolas", 32, "bold"))
        self.style.configure("Status.TLabel", background=c["bg"],
                             foreground=c["status"],
                             font=("Segoe UI", 9))
        self.style.configure("TButton", background=c["btn_bg"],
                             foreground=c["fg"],
                             font=("Segoe UI", 10, "bold"), padding=8)
        self.style.map("TButton",
                        background=[("active", c["accent"]),
                                    ("disabled", c["disabled"])],
                        foreground=[("active", c["btn_active"])])
        self.style.configure("Rec.TButton", background=c["rec_bg"],
                             foreground="#ffffff")
        self.style.map("Rec.TButton",
                        background=[("active", c["rec_active"])])
        self.style.configure("Stop.TButton", background=c["stop_bg"],
                             foreground="#ffffff")
        self.style.map("Stop.TButton",
                        background=[("active", c["stop_active"]),
                                    ("disabled", c["disabled"])])
        self.style.configure("TCombobox",
                             fieldbackground=c["btn_bg"],
                             background=c["btn_bg"],
                             foreground=c["fg"],
                             arrowcolor=c["accent"],
                             selectbackground=c["accent"],
                             selectforeground="#ffffff")
        self.style.map("TCombobox",
                        fieldbackground=[("readonly", c["btn_bg"]),
                                         ("disabled", c["disabled"])],
                        foreground=[("readonly", c["fg"]),
                                    ("disabled", c["muted"])],
                        selectbackground=[("readonly", c["accent"])],
                        selectforeground=[("readonly", "#ffffff")])
        self.style.configure("TCheckbutton", background=c["bg"],
                             foreground=c["fg"])
        self.style.map("TCheckbutton",
                        background=[("active", c["bg"])])

        # Entry style for the readonly path field
        self.style.configure("TEntry",
                             fieldbackground=c["btn_bg"],
                             foreground=c["fg"])
        self.style.map("TEntry",
                        fieldbackground=[("readonly", c["btn_bg"]),
                                         ("disabled", c["disabled"])],
                        foreground=[("readonly", c["fg"]),
                                    ("disabled", c["muted"])])

        # Update non-ttk widgets
        if hasattr(self, 'canvas'):
            self.canvas.configure(bg=c["canvas_bg"])

    # ── UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        main = ttk.Frame(self.root, padding=20)
        main.pack(fill="both", expand=True)

        # Header with theme toggle
        header_frame = ttk.Frame(main)
        header_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(header_frame, text="🎙  RecordAI",
                   style="Header.TLabel").pack(side="left")
        self.theme_btn = ttk.Button(header_frame, text="🌙",
                                     width=4, command=self._toggle_theme)
        self.theme_btn.pack(side="right")

        # ── Microphone selector ──────────────────────────────────────
        ttk.Label(main, text="Microphone:").pack(anchor="w")
        self.mic_combo = ttk.Combobox(main, state="readonly", width=52)
        self.mic_combo.pack(fill="x", pady=(2, 10))

        btn_row = ttk.Frame(main)
        btn_row.pack(fill="x", pady=(0, 4))
        ttk.Button(btn_row, text="↻ Refresh", width=12,
                   command=self._populate_devices).pack(side="left")

        # ── Format selector ─────────────────────────────────────────
        fmt_frame = ttk.Frame(main)
        fmt_frame.pack(fill="x", pady=(8, 0))
        ttk.Label(fmt_frame, text="Format:").pack(side="left")
        self.fmt_combo = ttk.Combobox(fmt_frame, textvariable=self.format_var,
                                       state="readonly", width=10,
                                       values=["WAV", "MP3"])
        self.fmt_combo.pack(side="left", padx=(6, 0))
        self.fmt_combo.bind("<<ComboboxSelected>>", self._on_format_change)
        # Ensure current format is visible
        self.fmt_combo.update_idletasks()

        if not HAS_LAME:
            self.fmt_combo.configure(state="disabled")
            self.format_var.set("WAV")
            ttk.Label(fmt_frame, text="(install lameenc for MP3)",
                       foreground=THEMES[self.current_theme]["muted"]
                       ).pack(side="left", padx=(8, 0))

        # ── Save location ────────────────────────────────────────────
        ttk.Label(main, text="Save to:").pack(anchor="w", pady=(10, 0))
        path_frame = ttk.Frame(main)
        path_frame.pack(fill="x", pady=(2, 10))

        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        fmt_ext = ".mp3" if self.format_var.get() == "MP3" else ".wav"
        self.path_var = tk.StringVar(
            value=os.path.join(downloads,
                               f"recording_{datetime.now():%Y%m%d_%H%M%S}{fmt_ext}"))
        self.path_entry = ttk.Entry(path_frame, textvariable=self.path_var,
                                     state="readonly", width=44)
        self.path_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(path_frame, text="Browse…", width=10,
                   command=self._choose_path).pack(side="right", padx=(6, 0))

        # ── Timer display ────────────────────────────────────────────
        self.timer_label = ttk.Label(main, text="00:00:00",
                                      style="Timer.TLabel")
        self.timer_label.pack(pady=(10, 4))

        # ── Volume meter ─────────────────────────────────────────────
        self.canvas = tk.Canvas(main, width=480, height=22,
                                 bg=THEMES[self.current_theme]["canvas_bg"],
                                 highlightthickness=0)
        self.canvas.pack(pady=(0, 8))
        self.vol_bar = self.canvas.create_rectangle(
            0, 0, 0, 22, fill=THEMES[self.current_theme]["meter_low"], width=0)

        # ── Status ───────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(main, textvariable=self.status_var,
                   style="Status.TLabel").pack(anchor="w")

        # ── Record / Stop toggle button ─────────────────────────────
        self.rec_btn = ttk.Button(main, text="●  Record",
                                   style="Rec.TButton",
                                   width=30, command=self._toggle_recording)
        self.rec_btn.pack(fill="x", pady=(14, 0))

        # ── Playback & folder buttons ────────────────────────────────
        action_frame = ttk.Frame(main)
        action_frame.pack(fill="x", pady=(10, 0))

        self.play_btn = ttk.Button(action_frame,
                                    text="▶  Play", width=14,
                                    command=self._play_last,
                                    state="disabled")
        self.play_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.folder_btn = ttk.Button(action_frame,
                                      text="📂  Open folder", width=16,
                                      command=self._open_save_folder)
        self.folder_btn.pack(side="right", expand=True, fill="x", padx=(4, 0))

    # ── Center window on screen ─────────────────────────────────────────
    def _center_window(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ── Theme toggle ────────────────────────────────────────────────────
    def _toggle_theme(self):
        new_theme = "light" if self.current_theme == "dark" else "dark"
        self.theme_btn.configure(text="☀" if new_theme == "light" else "🌙")
        self._configure_styles(new_theme)

    # ── Devices ─────────────────────────────────────────────────────────
    def _populate_devices(self):
        devices = sd.query_devices()
        self.mic_list = []
        names = []
        for idx, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                label = (f"[{idx}] {dev['name']}  "
                         f"({dev['max_input_channels']} ch, "
                         f"{int(dev['default_samplerate'])} Hz)")
                self.mic_list.append(idx)
                names.append(label)

        self.mic_combo["values"] = names
        if names:
            # Try to pick a sensible default (first real mic)
            default_idx = sd.default.device[0]
            if default_idx is not None and default_idx in self.mic_list:
                self.mic_combo.current(self.mic_list.index(default_idx))
            else:
                self.mic_combo.current(0)
        else:
            self.mic_combo["values"] = ["No input devices found"]
            self.mic_combo.current(0)
        # Force redraw so selected text is visible on Windows
        self.mic_combo.update_idletasks()

    # ── Format change handler ─────────────────────────────────────────
    def _on_format_change(self, _event=None):
        """Update file path extension when format changes."""
        ext = ".wav" if self.format_var.get() == "WAV" else ".mp3"
        current = self.path_var.get()
        base, _ = os.path.splitext(current)
        self.path_var.set(base + ext)

    # ── Path chooser ────────────────────────────────────────────────────
    def _choose_path(self):
        fmt = self.format_var.get()
        if fmt == "MP3":
            ext, ftypes = ".mp3", [("MP3 audio", "*.mp3"), ("WAV audio", "*.wav")]
        else:
            ext, ftypes = ".wav", [("WAV audio", "*.wav"), ("MP3 audio", "*.mp3")]

        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        path = filedialog.asksaveasfilename(
            title="Choose save location",
            defaultextension=ext,
            filetypes=ftypes,
            initialdir=downloads,
            initialfile=f"recording_{datetime.now():%Y%m%d_%H%M%S}{ext}"
        )
        if path:
            self.path_var.set(path)

    # ── Recording ───────────────────────────────────────────────────────
    def _toggle_recording(self):
        if not self.is_recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        if not self.mic_list:
            messagebox.showerror("Error", "No microphone available.")
            return

        sel = self.mic_combo.current()
        if sel < 0 or sel >= len(self.mic_list):
            messagebox.showerror("Error", "Please select a microphone.")
            return

        device_idx = self.mic_list[sel]
        dev_info = sd.query_devices(device_idx)
        self.sample_rate = int(dev_info["default_samplerate"])
        channels = min(dev_info["max_input_channels"], 1)  # mono

        save_path = self.path_var.get().strip()
        if not save_path:
            messagebox.showwarning("Warning", "Please choose a save location.")
            return

        # Ensure the directory exists
        directory = os.path.dirname(save_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as e:
                messagebox.showerror("Error",
                                     f"Cannot create directory:\n{e}")
                return

        # Reset state
        self.audio_frames = []
        self.is_recording = True
        self.start_time = time.time()

        # Switch button to Stop mode
        self.rec_btn.configure(text="■  Stop & Save", style="Stop.TButton")
        self.status_var.set("● Recording…")

        # Start audio stream in a background thread
        self.record_thread = threading.Thread(
            target=self._record_loop,
            args=(device_idx, channels),
            daemon=True
        )
        self.record_thread.start()
        self._update_timer()

    def _record_loop(self, device_idx: int, channels: int):
        """Runs in a background thread — captures audio blocks."""
        block_size = 1024
        try:
            with sd.InputStream(
                device=device_idx,
                samplerate=self.sample_rate,
                channels=channels,
                dtype="float32",
                blocksize=block_size,
                callback=self._audio_callback
            ):
                while self.is_recording:
                    sd.sleep(100)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(
                "Recording Error", f"Failed to record audio:\n{e}"))
            self.is_recording = False
            self.root.after(0, self._reset_ui)

    def _audio_callback(self, indata: np.ndarray, frames: int,
                         time_info, status):
        """Called by sounddevice for each audio block."""
        if status:
            print(f"Audio status: {status}")
        # Store a copy of the block
        self.audio_frames.append(indata.copy())

        # Update volume meter (RMS level)
        rms = float(np.sqrt(np.mean(indata ** 2)))
        self.root.after(0, self._update_meter, rms)

    def _update_meter(self, rms: float):
        c = THEMES[self.current_theme]
        max_w = 480
        width = int(min(rms / 0.3, 1.0) * max_w)
        color = (c["meter_low"] if rms < 0.15
                 else (c["meter_mid"] if rms < 0.25
                       else c["meter_high"]))
        self.canvas.itemconfigure(self.vol_bar, fill=color)
        self.canvas.coords(self.vol_bar, 0, 0, width, 22)

    def _update_timer(self):
        if not self.is_recording:
            return
        elapsed = time.time() - self.start_time
        h = int(elapsed // 3600)
        m = int((elapsed % 3600) // 60)
        s = int(elapsed % 60)
        self.timer_label.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
        self.timer_id = self.root.after(500, self._update_timer)

    def _stop_recording(self):
        if not self.is_recording:
            return

        self.is_recording = False
        self.status_var.set("Saving…")
        self.rec_btn.configure(state="disabled")

        # Poll the thread instead of blocking join()
        self._wait_for_thread()

    def _wait_for_thread(self):
        """Non-blocking wait for the recording thread to finish."""
        if self.record_thread and self.record_thread.is_alive():
            self.root.after(100, self._wait_for_thread)
        else:
            self._save_file()
            self._reset_ui()

    def _save_file(self):
        if not self.audio_frames:
            self.status_var.set("Nothing recorded.")
            return

        save_path = self.path_var.get().strip()
        try:
            audio_data = np.concatenate(self.audio_frames, axis=0)
            # Convert float32 [-1, 1] to int16 PCM
            pcm = (audio_data * 32767).astype(np.int16)
            channels = pcm.shape[1] if pcm.ndim > 1 else 1
            duration = len(pcm) / self.sample_rate

            ext = os.path.splitext(save_path)[1].lower()

            if ext == ".mp3":
                self._save_mp3(save_path, pcm, channels)
            else:
                self._save_wav(save_path, pcm, channels)

            self.last_saved_path = save_path
            self.play_btn.configure(state="normal")

            size_kb = os.path.getsize(save_path) / 1024
            self.status_var.set(
                f"Saved: {os.path.basename(save_path)}  "
                f"({duration:.1f}s, {size_kb:.0f} KB)")

            # Auto-generate a new filename for the next recording
            ext = os.path.splitext(save_path)[1]
            folder = os.path.dirname(save_path)
            self.path_var.set(
                os.path.join(folder,
                             f"recording_{datetime.now():%Y%m%d_%H%M%S}{ext}"))
        except Exception as e:
            messagebox.showerror("Save Error",
                                 f"Failed to save audio file:\n{e}")
            self.status_var.set("Save failed.")

    def _save_wav(self, path: str, pcm: np.ndarray, channels: int):
        """Save PCM data as a WAV file."""
        with wave.open(path, "w") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm.tobytes())

    def _save_mp3(self, path: str, pcm: np.ndarray, channels: int):
        """Encode PCM data and save as an MP3 file using lameenc."""
        if not HAS_LAME:
            raise RuntimeError("lameenc is not installed. Install it with:\n"
                               "  pip install lameenc")
        encoder = lameenc.Encoder()
        encoder.set_bit_rate(192)
        encoder.set_in_sample_rate(self.sample_rate)
        encoder.set_channels(channels)
        encoder.set_quality(2)  # 2 = high quality

        mp3_data = encoder.encode(pcm.tobytes())
        mp3_data += encoder.flush()

        with open(path, "wb") as f:
            f.write(mp3_data)

    # ── Playback & Folder ───────────────────────────────────────────────
    def _play_last(self):
        """Open the last recorded file with the system default player."""
        if not self.last_saved_path or not os.path.isfile(self.last_saved_path):
            messagebox.showinfo("Info", "No recorded file found.")
            return
        try:
            os.startfile(self.last_saved_path)
        except Exception as e:
            messagebox.showerror("Playback Error",
                                 f"Cannot open file:\n{e}")

    def _open_save_folder(self):
        """Open the current save directory in Windows Explorer."""
        save_path = self.path_var.get().strip()
        folder = os.path.dirname(save_path) if save_path else os.path.expanduser("~")
        if not os.path.isdir(folder):
            folder = os.path.expanduser("~")
        try:
            os.startfile(folder)
        except Exception as e:
            messagebox.showerror("Error",
                                 f"Cannot open folder:\n{e}")

    def _reset_ui(self):
        self.rec_btn.configure(state="normal", text="●  Record",
                                style="Rec.TButton")
        self.timer_label.configure(text="00:00:00")
        self.canvas.coords(self.vol_bar, 0, 0, 0, 22)
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None
        if "Saving" not in self.status_var.get() and \
           "Saved" not in self.status_var.get():
            self.status_var.set("Ready")

    def _on_close(self):
        """Clean shutdown — stop recording before closing."""
        if self.is_recording:
            self.is_recording = False
            if self.record_thread and self.record_thread.is_alive():
                self.record_thread.join(timeout=2)
        self.root.destroy()


# ── Entry point ─────────────────────────────────────────────────────────
def main():
    root = tk.Tk()

    # Try to set DPI awareness for sharp text on Windows 10
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = RecordAIApp(root)  # noqa: F841 — keeps reference alive
    root.mainloop()


if __name__ == "__main__":
    main()
