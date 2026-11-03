"""The application window.

Every string the user sees is in Indonesian and lives in this file; the code
around it is in English, the same split the other KelvianLab tools use.
"""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .core import media
from .core.pipeline import process_video
from .core.settings import ALL_QUALITIES, FAST, THOROUGH

VERSION = "1.0.0"
GREEN = "#1b7f3b"
ORANGE = "#b25e00"
RED = "#b3261e"
GREY = "#5f6368"


def _shorten(text: str, width: int = 86) -> str:
    return text if len(text) <= width else "…" + text[-(width - 1):]


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Video ke Teks {VERSION}")
        self.minsize(720, 0)
        self.resizable(True, False)

        self.location = tk.StringVar()
        self.quality = tk.StringVar(value=FAST.code)
        self.use_gpu = tk.BooleanVar(value=True)
        self.quality_note = tk.StringVar(value=FAST.explanation)
        self.status = tk.StringVar(value="Pilih video atau folder, lalu tekan Mulai.")
        self.detail = tk.StringVar(value=" ")

        self._messages: queue.Queue = queue.Queue()
        self._worker: threading.Thread | None = None
        self._stop_requested = threading.Event()
        self._results: list = []

        self._build()
        self.quality.trace_add("write", lambda *_: self._update_note())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(120, self._drain_messages)

    @property
    def busy(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        bold = ("Segoe UI", 10, "bold")

        ttk.Label(frame, text="1.  Video yang mau disalin jadi teks", font=bold).grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Entry(frame, textvariable=self.location).grid(row=1, column=0, sticky="ew", pady=(2, 2))
        self.pick_video_button = ttk.Button(frame, text="Pilih video…", command=self._pick_video)
        self.pick_video_button.grid(row=1, column=1, padx=(8, 0), pady=(2, 2))
        self.pick_folder_button = ttk.Button(frame, text="Pilih folder…", command=self._pick_folder)
        self.pick_folder_button.grid(row=1, column=2, padx=(6, 0), pady=(2, 2))
        ttk.Label(
            frame,
            text="Kalau memilih folder, semua video di dalamnya dikerjakan satu per satu.",
            foreground=GREY,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 12))

        ttk.Label(frame, text="2.  Pilih mutu pengerjaan", font=bold).grid(
            row=3, column=0, columnspan=3, sticky="w"
        )
        choices = ttk.Frame(frame)
        choices.grid(row=4, column=0, columnspan=3, sticky="w", pady=(2, 0))
        for preset in ALL_QUALITIES:
            ttk.Radiobutton(
                choices, text=preset.label, value=preset.code, variable=self.quality
            ).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(
            choices, text="Pakai kartu grafis NVIDIA kalau ada", variable=self.use_gpu
        ).pack(side="left")
        ttk.Label(
            frame, textvariable=self.quality_note, foreground=GREY,
            wraplength=660, justify="left",
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(2, 12))

        ttk.Label(
            frame,
            text=(
                "Hasilnya perkiraan mesin, bukan salinan yang dijamin tepat. Suara bising "
                "dan tulisan kecil atau cepat bisa salah atau terlewat. Video Anda tidak "
                "dikirim ke internet dan tidak diubah."
            ),
            foreground=GREY, wraplength=660, justify="left",
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(0, 12))

        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=0, columnspan=3, sticky="w")
        self.start_button = ttk.Button(buttons, text="3.  Mulai", command=self._start)
        self.start_button.pack(side="left", ipadx=14, ipady=4)
        self.stop_button = ttk.Button(
            buttons, text="Hentikan", command=self._request_stop, state="disabled"
        )
        self.stop_button.pack(side="left", padx=8, ipady=4)

        self.bar = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.bar.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(14, 6))
        self.status_label = ttk.Label(frame, textvariable=self.status, font=bold, wraplength=660)
        self.status_label.grid(row=9, column=0, columnspan=3, sticky="w")
        ttk.Label(frame, textvariable=self.detail, foreground=GREY).grid(
            row=10, column=0, columnspan=3, sticky="w", pady=(2, 8)
        )

        self.summary = tk.Text(frame, height=9, wrap="word", relief="flat", background="#f6f6f6")
        self.summary.grid(row=11, column=0, columnspan=3, sticky="ew")
        self.summary.configure(state="disabled")

        afterwards = ttk.Frame(frame)
        afterwards.grid(row=12, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.open_button = ttk.Button(
            afterwards, text="Buka folder hasil", command=self._open_folder, state="disabled"
        )
        self.open_button.pack(side="left")

    def _update_note(self) -> None:
        preset = THOROUGH if self.quality.get() == THOROUGH.code else FAST
        self.quality_note.set(preset.explanation)

    def _pick_video(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Pilih video",
            filetypes=[
                ("Video", "*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.wmv *.flv"),
                ("Semua berkas", "*.*"),
            ],
        )
        if chosen:
            self.location.set(chosen)

    def _pick_folder(self) -> None:
        chosen = filedialog.askdirectory(title="Pilih folder berisi video")
        if chosen:
            self.location.set(chosen)

    def _set_summary(self, text: str) -> None:
        self.summary.configure(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", text)
        self.summary.configure(state="disabled")

    def _lock(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        for button in (self.start_button, self.pick_video_button, self.pick_folder_button):
            button.configure(state=state)
        self.stop_button.configure(state="normal" if running else "disabled")

    def _start(self) -> None:
        location = self.location.get().strip()
        if not location:
            messagebox.showinfo("Video ke Teks", "Pilih video atau folder dulu.")
            return
        if not media.ffmpeg_available():
            messagebox.showerror(
                "Video ke Teks",
                "ffmpeg tidak ditemukan di komputer ini.\n\n"
                "Aplikasi ini memakai ffmpeg untuk membaca video. Pasang dulu ffmpeg, "
                "lalu buka aplikasi ini lagi.",
            )
            return

        videos = media.find_videos(Path(location))
        if not videos:
            messagebox.showwarning(
                "Video ke Teks",
                "Tidak ada berkas video yang ditemukan di tempat itu.\n\n"
                "Yang bisa dibaca: mp4, mkv, mov, avi, webm, m4v, wmv, flv.",
            )
            return

        preset = THOROUGH if self.quality.get() == THOROUGH.code else FAST
        if not messagebox.askyesno(
            "Video ke Teks",
            f"{len(videos)} video akan dikerjakan dengan mutu {preset.label}.\n\n"
            f"Kalau model suara {preset.speech_model} belum ada di komputer ini, "
            f"model itu diunduh dulu sekitar {preset.download_size}. Unduhan hanya sekali.\n\n"
            "Lanjutkan?",
        ):
            return

        self._stop_requested.clear()
        self._results = []
        self._set_summary("")
        self.open_button.configure(state="disabled")
        self.status_label.configure(foreground="")
        self.bar["value"] = 0
        self._lock(True)

        self._worker = threading.Thread(target=self._work, args=(videos, preset), daemon=True)
        self._worker.start()

    def _work(self, videos, preset) -> None:
        try:
            for position, video in enumerate(videos, start=1):
                if self._stop_requested.is_set():
                    break
                self._messages.put(("title", f"Video {position} dari {len(videos)}: {video.name}"))
                result = process_video(
                    video,
                    preset,
                    use_gpu=self.use_gpu.get(),
                    report=lambda message: self._messages.put(("detail", message)),
                    should_stop=self._stop_requested.is_set,
                )
                self._messages.put(("result", result))
                self._messages.put(("progress", position / len(videos) * 100))
        except Exception as error:
            self._messages.put(("crash", f"{type(error).__name__}: {error}"))
        finally:
            self._messages.put(("finished", None))

    def _request_stop(self) -> None:
        self._stop_requested.set()
        self.stop_button.configure(state="disabled")
        self.status.set("Menghentikan… menunggu video yang sedang dikerjakan selesai.")

    def _drain_messages(self) -> None:
        while True:
            try:
                kind, payload = self._messages.get_nowait()
            except queue.Empty:
                break
            if kind == "title":
                self.status.set(payload)
            elif kind == "detail":
                self.detail.set(_shorten(payload))
            elif kind == "progress":
                self.bar["value"] = payload
            elif kind == "result":
                self._results.append(payload)
                self._set_summary(self._build_summary())
            elif kind == "crash":
                self.status_label.configure(foreground=RED)
                self.status.set("Terjadi galat yang tidak terduga.")
                self._set_summary(str(payload))
            elif kind == "finished":
                self._finish()
        self.after(120, self._drain_messages)

    def _build_summary(self) -> str:
        lines = []
        for result in self._results:
            if result.error:
                lines.append(f"GAGAL  {result.video.name}")
                lines.append(f"       {result.error}")
                continue
            device = "GPU" if result.used_gpu else "CPU"
            lines.append(f"SELESAI  {result.video.name}  ({device})")
            lines.append(
                f"         suara {result.speech_count} potongan, "
                f"layar {result.screen_count} tampilan "
                f"(dari {result.frames_checked} gambar, {result.frames_read} perlu dibaca)"
            )
            for note in result.notes:
                lines.append(f"         catatan: {note}")
            if result.txt_file:
                lines.append(
                    f"         hasil: {result.txt_file.name} dan {result.srt_file.name}"
                )
        return "\n".join(lines)

    def _finish(self) -> None:
        if self.busy:
            return
        self._lock(False)
        self.detail.set(" ")
        done = [r for r in self._results if not r.error]
        failed = [r for r in self._results if r.error]

        if self._stop_requested.is_set():
            self.status_label.configure(foreground=ORANGE)
            self.status.set(
                f"Dihentikan. {len(done)} video sudah selesai dan hasilnya tersimpan."
            )
        elif failed and not done:
            self.status_label.configure(foreground=RED)
            self.status.set("Tidak ada video yang berhasil dikerjakan.")
        elif failed:
            self.status_label.configure(foreground=ORANGE)
            self.status.set(f"Selesai. {len(done)} video berhasil, {len(failed)} gagal.")
        elif done:
            self.status_label.configure(foreground=GREEN)
            self.status.set(f"Selesai. {len(done)} video tersalin jadi teks.")
            self.bar["value"] = 100
        if done:
            self.open_button.configure(state="normal")

    def _open_folder(self) -> None:
        for result in self._results:
            if result.txt_file:
                os.startfile(result.txt_file.parent)  # type: ignore[attr-defined]
                return

    def _on_close(self) -> None:
        if not self.busy:
            self.destroy()
            return
        if messagebox.askyesno(
            "Video ke Teks",
            "Masih ada video yang sedang dikerjakan.\n\nHentikan dan tutup? "
            "Video yang sudah selesai hasilnya tetap tersimpan.",
        ):
            self._stop_requested.set()
            self.destroy()


def _sharp_text_on_high_dpi() -> None:
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass  # not Windows, or an old one; the window just looks slightly blurry


def run_app() -> None:
    _sharp_text_on_high_dpi()
    App().mainloop()
