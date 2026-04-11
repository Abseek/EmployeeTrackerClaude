import io
import threading
import urllib.request
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from config import COLOR_CARD, COLOR_BORDER, COLOR_TEXT_MUTED, COLOR_ACCENT

THUMB_W = 200
THUMB_H = 112  # 16:9

# Limit concurrent thumbnail downloads to avoid thread pile-up during long sessions
_THUMB_SEMAPHORE = threading.Semaphore(3)


def _load_pil_image(item) -> Image.Image:
    """Open a PIL Image from a local Path or an HTTPS URL string."""
    if isinstance(item, str):
        with urllib.request.urlopen(item, timeout=15) as resp:
            return Image.open(io.BytesIO(resp.read()))
    return Image.open(str(item))


def _item_name(item) -> str:
    """Return a display name (timestamp portion) for a Path or URL."""
    if isinstance(item, str):
        name = item.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    else:
        name = item.stem
    return name.split("_", 1)[-1].replace("-", ":")


class ScreenshotGallery(ctk.CTkScrollableFrame):
    """Grid of screenshot thumbnails. Click to open full-size viewer."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._thumbs: dict = {}   # idx → CTkImage, keeps refs alive
        self._paths: list = []

    def load_screenshots(self, paths: list):
        """Display placeholder cards immediately, then load thumbnails in background."""
        for w in self.winfo_children():
            w.destroy()
        self._thumbs.clear()
        self._paths = list(paths)

        if not paths:
            ctk.CTkLabel(
                self,
                text="No screenshots for this date.",
                text_color=COLOR_TEXT_MUTED,
                font=ctk.CTkFont(size=12),
            ).grid(row=0, column=0, padx=20, pady=20)
            return

        cols = 4
        for idx, item in enumerate(paths):
            row = idx // cols
            col = idx % cols
            placeholder = self._make_card(item, idx, row, col)
            # Load image in a background thread
            threading.Thread(
                target=self._load_thumb_bg,
                args=(item, idx, placeholder),
                daemon=True,
            ).start()

    def _make_card(self, item, idx: int, row: int, col: int) -> ctk.CTkLabel:
        """Create a card with a 'Loading…' placeholder; return the placeholder label."""
        card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

        placeholder = ctk.CTkLabel(
            card,
            text="Loading…",
            width=THUMB_W,
            height=THUMB_H,
            text_color=COLOR_TEXT_MUTED,
            font=ctk.CTkFont(size=10),
        )
        placeholder.pack(padx=4, pady=(4, 0))
        placeholder.bind("<Button-1>", lambda e, i=idx: self._open_fullscreen(i))

        ctk.CTkLabel(
            card,
            text=_item_name(item),
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_MUTED,
        ).pack(pady=(2, 4))

        return placeholder

    def _load_thumb_bg(self, item, idx: int, placeholder: ctk.CTkLabel):
        """Background thread: fetch/open image, then hand off to main thread."""
        with _THUMB_SEMAPHORE:
            try:
                img = _load_pil_image(item)
                img.thumbnail((THUMB_W, THUMB_H))
                if self.winfo_exists() and placeholder.winfo_exists():
                    self.after(
                        0,
                        lambda i=img, ix=idx, pl=placeholder: self._set_thumb(i, ix, pl),
                    )
            except Exception:
                pass

    def _set_thumb(self, img: Image.Image, idx: int, placeholder: ctk.CTkLabel):
        """Main thread: create CTkImage and update the placeholder label."""
        if not self.winfo_exists() or not placeholder.winfo_exists():
            return
        ctk_img = ctk.CTkImage(img, size=(THUMB_W, THUMB_H))
        self._thumbs[idx] = ctk_img  # keep ref alive
        placeholder.configure(image=ctk_img, text="")

    def _open_fullscreen(self, idx: int):
        viewer = FullscreenViewer(self, self._paths, idx)
        viewer.grab_set()


class FullscreenViewer(ctk.CTkToplevel):
    def __init__(self, master, paths: list, start_idx: int):
        super().__init__(master)
        self.title("Screenshot Viewer")
        self.geometry("1000x680")
        self.configure(fg_color="#0d0d1a")
        self._paths = paths
        self._idx = start_idx
        self._img_ref = None

        self._img_label = ctk.CTkLabel(self, text="", fg_color="transparent")
        self._img_label.pack(fill="both", expand=True, padx=12, pady=(12, 0))

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", padx=12, pady=8)

        ctk.CTkButton(nav, text="← Prev", width=90, command=self._prev).pack(side="left")
        self._counter_label = ctk.CTkLabel(nav, text="", text_color=COLOR_TEXT_MUTED)
        self._counter_label.pack(side="left", expand=True)
        ctk.CTkButton(nav, text="Next →", width=90, command=self._next).pack(side="right")

        self.bind("<Left>", lambda e: self._prev())
        self.bind("<Right>", lambda e: self._next())
        self.bind("<Escape>", lambda e: self.destroy())

        self._load()

    def _load(self):
        item = self._paths[self._idx]
        self._img_label.configure(text="Loading…", image=None)
        self._counter_label.configure(
            text=f"{self._idx + 1} / {len(self._paths)}  —  {_item_name(item)}"
        )
        threading.Thread(target=self._load_bg, args=(item,), daemon=True).start()

    def _load_bg(self, item):
        try:
            img = _load_pil_image(item)
            max_w, max_h = 960, 580
            img.thumbnail((max_w, max_h))
            if self.winfo_exists():
                self.after(0, lambda i=img: self._set_image(i))
        except Exception:
            if self.winfo_exists():
                self.after(0, lambda: self._img_label.configure(
                    text="Could not load image.", image=None
                ))

    def _set_image(self, img: Image.Image):
        if not self.winfo_exists():
            return
        self._img_ref = ctk.CTkImage(img, size=img.size)
        self._img_label.configure(image=self._img_ref, text="")

    def _prev(self):
        if self._idx > 0:
            self._idx -= 1
            self._load()

    def _next(self):
        if self._idx < len(self._paths) - 1:
            self._idx += 1
            self._load()
