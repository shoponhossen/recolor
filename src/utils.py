import numpy as np
from PIL import Image, ImageOps
import io
import os
from pathlib import Path
import flet as ft


def get_projects_dir(page: ft.Page) -> Path:
    if page.platform == ft.PagePlatform.ANDROID:
        # App-private storage: no permissions needed, works on every Android version
        base = Path(os.environ["FLET_APP_STORAGE_DATA"])
    else:
        # Windows / Linux: a visible, user-friendly location
        base = Path.home() / "Documents"

    projects = base / "ReColor" / "projects"
    projects.mkdir(parents=True, exist_ok=True)
    return projects


def load_rgba(path) -> np.ndarray:
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)  # fix phone photo rotation
        return np.array(im.convert("RGBA"))  # (H, W, 4) uint8


def save_rgba(arr: np.ndarray, path, quality: int = 95) -> None:
    im = Image.fromarray(arr, "RGBA")
    if str(path).lower().endswith((".jpg", ".jpeg")):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.getchannel("A"))
        im = bg
    im.save(path, quality=quality)


def arr_to_bytes(arr):
    pil_img = Image.fromarray(arr, mode="RGBA")
    img_byte_arr = io.BytesIO()
    pil_img.save(img_byte_arr, format="PNG")
    img_bytes = img_byte_arr.getvalue()
    return img_bytes
