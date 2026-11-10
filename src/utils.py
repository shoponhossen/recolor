import numpy as np
from PIL import Image, ImageOps
import io
import os
import base64
from pathlib import Path
import cv2
import flet as ft


def get_projects_dir(page: ft.Page | None = None) -> Path:
    if page is not None and getattr(page, "platform", None) == ft.PagePlatform.ANDROID:
        base = Path(os.environ.get("FLET_APP_STORAGE_DATA", str(Path.home() / "Documents")))
    else:
        base = Path.home() / "Documents"

    projects = base / "ReColor" / "projects"
    projects.mkdir(parents=True, exist_ok=True)
    return projects


def load_rgba(path: str | Path) -> np.ndarray:
    """Load image from disk and return (H, W, 4) uint8 RGBA array."""
    with Image.open(str(path)) as im:
        im = ImageOps.exif_transpose(im)  # fix phone photo rotation
        return np.array(im.convert("RGBA"), dtype=np.uint8)


def save_rgba(arr: np.ndarray, path: str | Path, quality: int = 95) -> None:
    """Save RGBA array to JPG or PNG file."""
    path_str = str(path).lower()
    if path_str.endswith((".jpg", ".jpeg")):
        # Blend over white background for JPEG
        if arr.shape[2] == 4:
            alpha = arr[..., 3:4].astype(np.float32) / 255.0
            rgb = arr[..., :3].astype(np.float32)
            white = np.ones_like(rgb) * 255.0
            composite = (rgb * alpha + white * (1.0 - alpha)).astype(np.uint8)
        else:
            composite = arr[..., :3]
        bgr = cv2.cvtColor(composite, cv2.COLOR_RGB2BGR)
        cv2.imwrite(str(path), bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    else:
        # PNG
        if arr.shape[2] == 4:
            bgra = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA)
        else:
            bgra = cv2.cvtColor(arr, cv2.COLOR_RGB2BGRA)
        cv2.imwrite(str(path), bgra)


def arr_to_jpeg_bytes(arr: np.ndarray, quality: int = 85) -> bytes:
    """Fast encoding of RGBA/RGB numpy array into JPEG bytes for Flet Image(src=...)."""
    if arr.ndim != 3:
        raise ValueError(f"Expected 3D array, got {arr.shape}")
    if arr.shape[2] == 4:
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    elif arr.shape[2] == 3:
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    else:
        bgr = arr

    ret, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ret:
        raise RuntimeError("Failed to encode image to JPEG")
    return buf.tobytes()


def arr_to_base64_jpeg(arr: np.ndarray, quality: int = 85) -> str:
    """Convert numpy RGBA or RGB image array into base64 JPEG string for Flet Image."""
    if arr.ndim != 3:
        raise ValueError(f"Expected 3D array, got {arr.shape}")
    if arr.shape[2] == 4:
        # Fast composite on black or transparent
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    elif arr.shape[2] == 3:
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    else:
        bgr = arr

    ret, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ret:
        raise RuntimeError("Failed to encode image to JPEG")
    return base64.b64encode(buf).decode("ascii")


def arr_to_bytes(arr: np.ndarray) -> bytes:
    """Legacy helper returning PNG bytes."""
    pil_img = Image.fromarray(arr, mode="RGBA")
    bio = io.BytesIO()
    pil_img.save(bio, format="PNG")
    return bio.getvalue()


def create_mask_overlay(
    arr: np.ndarray,
    mask: np.ndarray,
    color: tuple[int, int, int] = (255, 55, 55),
    opacity: float = 0.45,
) -> np.ndarray:
    """
    Renders a Lightroom-style red rubylith mask overlay on top of an RGBA image array.
    Optimized for high performance and minimal memory allocations.
    arr: (H, W, 4) uint8
    mask: (H, W) float32 in [0, 1]
    """
    h, w = arr.shape[:2]
    if mask.shape[:2] != (h, w):
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)

    if not np.any(mask):
        return arr.copy()

    out = arr.copy()
    alpha = (np.clip(mask, 0.0, 1.0) * float(opacity))[..., None]
    rgb = out[..., :3].astype(np.float32)
    tint = np.array(color[:3], dtype=np.float32)
    rgb += (tint - rgb) * alpha
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    return out
