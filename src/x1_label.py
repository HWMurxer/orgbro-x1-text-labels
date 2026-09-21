from __future__ import annotations

import json
import os
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import serial
from serial.tools import list_ports
from PIL import Image, ImageDraw, ImageFont, ImageTk


LABEL_W = 280
LABEL_H = 96
RASTER_W = 96
RASTER_H = 280
PRINT_HEAD_OFFSET = 17  # 9 captured default + 8 dots (about 1 mm) downward


def settings_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home()))
    return base / "ORGBRO-X1-Textetiketten" / "settings.json"


def load_saved_lines(path: Path | None = None) -> list[str]:
    target = path or settings_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        lines = data.get("lines", [])
        if isinstance(lines, list):
            return [str(value) for value in lines[:3]] + [""] * max(0, 3 - len(lines))
    except (OSError, ValueError, TypeError):
        pass
    return ["", "", ""]


def save_lines(lines: list[str], path: Path | None = None) -> None:
    target = path or settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"lines": list(lines[:3])}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _font_path() -> str:
    for candidate in (
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
        Path(r"C:\Windows\Fonts\segoeuib.ttf"),
    ):
        if candidate.exists():
            return str(candidate)
    raise RuntimeError("Keine geeignete Windows-Schrift gefunden.")


def render_label(lines: list[str]) -> Image.Image:
    lines = [line.strip() for line in lines if line.strip()]
    if not lines:
        raise ValueError("Bitte mindestens eine Textzeile eingeben.")
    if len(lines) > 3:
        raise ValueError("Es sind höchstens drei Textzeilen möglich.")

    canvas = Image.new("L", (LABEL_W, LABEL_H), 255)
    draw = ImageDraw.Draw(canvas)
    # Keep a calm, practical safety margin at both tear edges.  The original
    # app also leaves substantially more horizontal whitespace than our first
    # maximally enlarged prototype did.
    # Use almost the full 40-mm label length. The earlier 64-dot side margins
    # were only a temporary diagnostic precaution and made longer words tiny.
    margin_x, margin_y, spacing = 12, 5, 2
    best = None
    for size in range(72, 9, -1):
        font = ImageFont.truetype(_font_path(), size)
        boxes = [draw.textbbox((0, 0), line, font=font, stroke_width=0) for line in lines]
        widths = [box[2] - box[0] for box in boxes]
        heights = [box[3] - box[1] for box in boxes]
        total_h = sum(heights) + spacing * (len(lines) - 1)
        if max(widths) <= LABEL_W - 2 * margin_x and total_h <= LABEL_H - 2 * margin_y:
            best = font, boxes, widths, heights, total_h
            break
    if best is None:
        raise ValueError("Der Text ist für das Etikett zu lang.")

    font, boxes, widths, heights, total_h = best
    y = (LABEL_H - total_h) // 2
    for line, box, width, height in zip(lines, boxes, widths, heights):
        x = (LABEL_W - width) // 2
        draw.text((x - box[0], y - box[1]), line, font=font, fill=0)
        y += height + spacing
    return canvas


def image_to_raster(label: Image.Image) -> bytes:
    # The X1 print head is 96 dots wide. The label image is transmitted turned
    # 90 degrees, exactly as observed in the XEasyLabel Bluetooth capture.
    image = label.transpose(Image.Transpose.ROTATE_90).convert("L")
    if image.size != (RASTER_W, RASTER_H):
        raise ValueError(f"Unerwartete Rastergröße: {image.size}")
    out = bytearray()
    pixels = image.load()
    for y in range(RASTER_H):
        for x0 in range(0, RASTER_W, 8):
            value = 0
            for bit in range(8):
                if pixels[x0 + bit, y] < 128:
                    value |= 1 << (7 - bit)
            out.append(value)
    return bytes(out)


def packet(command: int, sequence: int, payload: bytes = b"") -> bytes:
    return (
        bytes((0x64, command, sequence))
        + len(payload).to_bytes(2, "little")
        + payload
        + b"\x00\x00\x00\x00\x9b"
    )


def build_job(label: Image.Image) -> tuple[bytes, bytes, bytes]:
    raster = image_to_raster(label)
    if len(raster) != 3360:
        raise ValueError(f"Unerwartete Bilddatenlänge: {len(raster)}")

    hello = packet(0x12, 0x01) + packet(0x11, 0x02)
    prepare = packet(0x72, 0x03, b"\x01")
    job = bytearray()
    job += packet(0x0A, 0x04, b"\x19")
    job += packet(0x09, 0x05, b"\x09")
    job += packet(0x03, 0x06, bytes.fromhex("02 20 03"))
    # Two-byte little-endian print origin. 09 00 means 9 dots; reversing this
    # to 00 09 means 2304 dots and advances about seven 40-mm labels.
    job += packet(0x02, 0x07, PRINT_HEAD_OFFSET.to_bytes(2, "little"))
    sequence = 0x08
    for offset in range(0, len(raster), 288):
        job += packet(0x00, sequence, raster[offset:offset + 288])
        sequence += 1
    job += packet(0x03, sequence, bytes.fromhex("01 20 03"))
    return hello, prepare, bytes(job)


def send_job(port_name: str, label: Image.Image, status) -> None:
    hello, prepare, job = build_job(label)
    with serial.Serial(port_name, 9600, timeout=0.05, write_timeout=5) as port:
        status("Drucker wird abgefragt …")
        port.write(hello)
        port.flush()
        # The captured manufacturer-app session leaves the printer time to
        # return its identity/status before paper setup begins.  Sending the
        # following commands too early can be interpreted as repeated feeds.
        time.sleep(1.05)
        identity = port.read(4096)
        if not identity:
            raise RuntimeError("Der X1 antwortet nicht. Ist er eingeschaltet und das Handy getrennt?")

        port.write(prepare)
        port.flush()
        time.sleep(1.05)
        port.read(4096)

        status("Etikett wird übertragen …")
        # Reproduce the successful capture replay exactly: RFCOMM blocks of
        # 255 bytes, a short pause, and a status read after every block.
        for offset in range(0, len(job), 255):
            port.write(job[offset:offset + 255])
            port.flush()
            time.sleep(0.03)
            port.read(4096)
        time.sleep(1.2)
        port.read(4096)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ORGBRO X1 – Textetiketten")
        self.resizable(False, False)
        self.configure(padx=18, pady=16)
        self._preview_photo = None

        ttk.Label(self, text="Text für das Etikett", font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        ttk.Button(self, text="Felder leeren", command=self.clear_fields).grid(
            row=0, column=2, sticky="e", pady=(0, 8)
        )
        self.entries = []
        saved_lines = load_saved_lines()
        for row in range(3):
            ttk.Label(self, text=f"Zeile {row + 1}").grid(row=row + 1, column=0, sticky="w", padx=(0, 8), pady=4)
            entry = ttk.Entry(self, width=42, font=("Segoe UI", 11))
            entry.grid(row=row + 1, column=1, columnspan=2, sticky="ew", pady=4)
            entry.bind("<KeyRelease>", lambda _event: self.update_preview())
            entry.insert(0, saved_lines[row])
            self.entries.append(entry)

        ttk.Label(self, text="Vorschau 14 × 40 mm").grid(row=4, column=0, columnspan=3, sticky="w", pady=(14, 5))
        self.preview = ttk.Label(self, relief="solid", borderwidth=1)
        self.preview.grid(row=5, column=0, columnspan=3)

        ttk.Label(self, text="Anschluss").grid(row=6, column=0, sticky="w", pady=(14, 0))
        self.port_var = tk.StringVar(value="COM5")
        self.port_box = ttk.Combobox(self, textvariable=self.port_var, width=12, state="readonly")
        self.port_box.grid(row=6, column=1, sticky="w", pady=(14, 0))
        ttk.Button(self, text="Aktualisieren", command=self.refresh_ports).grid(row=6, column=2, sticky="e", pady=(14, 0))

        self.print_button = ttk.Button(self, text="Etikett drucken", command=self.start_print)
        self.print_button.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(16, 8), ipady=5)
        self.status_var = tk.StringVar(value="Bereit")
        ttk.Label(self, textvariable=self.status_var).grid(row=8, column=0, columnspan=3, sticky="w")

        self.refresh_ports()
        self.update_preview()
        self.entries[0].focus_set()
        self.protocol("WM_DELETE_WINDOW", self.close_app)

    def lines(self) -> list[str]:
        return [entry.get() for entry in self.entries]

    def clear_fields(self) -> None:
        for entry in self.entries:
            entry.delete(0, tk.END)
        save_lines(self.lines())
        self.update_preview()
        self.entries[0].focus_set()

    def close_app(self) -> None:
        save_lines(self.lines())
        self.destroy()

    def update_preview(self) -> None:
        try:
            label = render_label(self.lines())
        except ValueError:
            label = Image.new("L", (LABEL_W, LABEL_H), 255)
        enlarged = label.resize((LABEL_W * 2, LABEL_H * 2), Image.Resampling.NEAREST)
        self._preview_photo = ImageTk.PhotoImage(enlarged)
        self.preview.configure(image=self._preview_photo)

    def refresh_ports(self) -> None:
        ports = [item.device for item in list_ports.comports()]
        self.port_box["values"] = ports
        if self.port_var.get() not in ports and ports:
            self.port_var.set("COM5" if "COM5" in ports else ports[0])

    def set_status(self, value: str) -> None:
        self.after(0, self.status_var.set, value)

    def start_print(self) -> None:
        try:
            lines_to_save = self.lines()
            label = render_label(lines_to_save)
            port = self.port_var.get()
            if not port:
                raise ValueError("Kein Anschluss ausgewählt.")
        except Exception as exc:
            messagebox.showerror("Eingabe prüfen", str(exc), parent=self)
            return
        self.print_button.configure(state="disabled")
        self.status_var.set("Druck wird vorbereitet …")

        def worker() -> None:
            try:
                send_job(port, label, self.set_status)
            except Exception as exc:
                self.after(0, messagebox.showerror, "Drucken fehlgeschlagen", str(exc), parent=self)
                self.set_status("Drucken fehlgeschlagen")
            else:
                save_lines(lines_to_save)
                self.set_status("Etikett wurde übertragen")
            finally:
                self.after(0, self.print_button.configure, {"state": "normal"})

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    App().mainloop()
