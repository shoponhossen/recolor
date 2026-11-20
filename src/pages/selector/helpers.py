import numpy as np
import cv2


def safe_at(obj, h: int, w: int) -> np.ndarray:
    """Safely resize a Mask or SubMask to (h, w) with fallback."""
    if obj is None:
        return np.ones((h, w), dtype=np.float32)
    data = obj.data if hasattr(obj, "data") else np.ones((h, w), dtype=np.float32)
    if data.shape[:2] == (h, w):
        return data
    return cv2.resize(data, (w, h), interpolation=cv2.INTER_LINEAR)


def load_target_buf(project, mi: int, si: int, ph: int, pw: int) -> np.ndarray:
    """Load the mask data for target layer `mi` and sub-mask `si` resized to (ph, pw)."""
    if mi >= len(project.layers):
        return np.zeros((ph, pw), dtype=np.float32)
    layer = project.layers[mi]
    if layer.mask is None:
        return (
            np.ones((ph, pw), dtype=np.float32)
            if mi == 0
            else np.zeros((ph, pw), dtype=np.float32)
        )
    if si == -1:
        return safe_at(layer.mask, ph, pw).copy()
    if 0 <= si < len(layer.mask.sub_masks):
        return safe_at(layer.mask.sub_masks[si], ph, pw).copy()
    return np.zeros((ph, pw), dtype=np.float32)


def apply_stroke_feather(
    buf: np.ndarray,
    points: list[tuple[float, float]],
    brush_sz: float,
    feather: float,
    h: int,
    w: int,
):
    """Feather only the bounding box region affected by the stroke, avoiding full-image GaussianBlur."""
    if not points:
        return
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    sigma = max(0.5, (brush_sz / 2.0) * feather * 0.5)
    pad = int(round(brush_sz + sigma * 3))

    x1 = max(0, int(round(min(xs))) - pad)
    y1 = max(0, int(round(min(ys))) - pad)
    x2 = min(w, int(round(max(xs))) + pad)
    y2 = min(h, int(round(max(ys))) + pad)

    if x2 <= x1 or y2 <= y1:
        return

    sub = buf[y1:y2, x1:x2]
    ksize = int(sigma * 4) | 1
    blurred = cv2.GaussianBlur(sub, (ksize, ksize), sigmaX=sigma)
    buf[y1:y2, x1:x2] = np.clip(blurred, 0.0, 1.0)


def map_coords_to_img(
    x: float, y: float, viewport: list[float], img_w: int, img_h: int
) -> tuple[float, float]:
    """Map touch/pointer canvas coordinates to preview image coordinates."""
    vw, vh = viewport[0], viewport[1]
    scale = min(vw / img_w, vh / img_h)
    rw, rh = img_w * scale, img_h * scale
    ox = (vw - rw) / 2.0
    oy = (vh - rh) / 2.0
    ix = (x - ox) / scale
    iy = (y - oy) / scale
    return (
        max(0.0, min(img_w - 1.0, ix)),
        max(0.0, min(img_h - 1.0, iy)),
    )
