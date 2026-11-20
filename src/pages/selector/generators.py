import numpy as np


def generate_radial_mask(
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    feather: float,
    deg: float,
    x_grid: np.ndarray,
    y_grid: np.ndarray,
    opacity: float = 1.0,
    invert: bool = False,
) -> np.ndarray:
    """Generate float32 radial elliptical mask in [0.0, 1.0]."""
    fth = float(np.clip(feather, 0.01, 0.99))
    rx_safe = max(1.0, float(rx))
    ry_safe = max(1.0, float(ry))

    dx = x_grid - cx
    dy = y_grid - cy
    if deg != 0.0:
        rad = np.radians(deg)
        cos_a, sin_a = np.cos(rad), np.sin(rad)
        xr = dx * cos_a + dy * sin_a
        yr = -dx * sin_a + dy * cos_a
    else:
        xr, yr = dx, dy

    dist = np.sqrt((xr / rx_safe) ** 2 + (yr / ry_safe) ** 2)
    inner = 1.0 - fth
    res = np.clip(1.0 - (dist - inner) / fth, 0.0, 1.0).astype(np.float32)
    if invert:
        res = 1.0 - res
    if opacity < 1.0:
        res = res * float(max(0.0, min(1.0, opacity)))
    return res.astype(np.float32)


def generate_linear_mask(
    cx: float,
    cy: float,
    feather: float,
    deg: float,
    x_grid: np.ndarray,
    y_grid: np.ndarray,
    span_base: float = 0.0,
    span: float = 0.0,
    opacity: float = 1.0,
    invert: bool = False,
) -> np.ndarray:
    """Generate smooth linear gradient mask with cubic falloff."""
    rad = np.radians(deg)
    ux, uy = np.cos(rad), np.sin(rad)
    if span > 0.0:
        eff_span = max(5.0, float(span))
    else:
        fth = float(np.clip(feather, 0.05, 0.95))
        eff_span = max(3.0, (span_base if span_base > 0 else 100.0) * fth)

    p = (x_grid - cx) * ux + (y_grid - cy) * uy
    t = np.clip(0.5 - p / eff_span, 0.0, 1.0)
    # Smooth Hermite interpolation (3t^2 - 2t^3)
    res = (t * t * (3.0 - 2.0 * t)).astype(np.float32)
    if invert:
        res = 1.0 - res
    if opacity < 1.0:
        res = res * float(max(0.0, min(1.0, opacity)))
    return res.astype(np.float32)


def generate_color_range_mask(
    rgb_img: np.ndarray,
    target_rgb: tuple[int, int, int],
    tolerance: float,
    feather: float = 0.2,
) -> np.ndarray:
    """Isolate pixels within Euclidean color distance tolerance."""
    rgb = rgb_img[..., :3].astype(np.float32)
    target = np.array(target_rgb[:3], dtype=np.float32)
    # Maximum Euclidean distance in RGB is sqrt(255^2 * 3) ~ 441.67
    dist = np.linalg.norm(rgb - target, axis=2) / 441.67
    tol = max(0.01, tolerance)
    f = max(0.01, feather)
    return np.clip(1.0 - (dist - tol * (1.0 - f)) / (tol * f), 0.0, 1.0).astype(
        np.float32
    )
