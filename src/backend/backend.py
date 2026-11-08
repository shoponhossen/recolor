import numpy as np
import cv2
import uuid


class SubMask:
    """A child mask that modifies the parent main mask.

    Erase mode:  final_mask = main * (1 - sub)
    Paint mode:  final_mask = main * sub
    """

    def __init__(
        self,
        data=None,
        size=None,
        mode: str = "erase",
        mask_type: str = "brush",
        name: str | None = None,
    ):
        self.id = uuid.uuid4().hex[:8]
        self.mode = mode  # "erase" | "paint"
        self.mask_type = mask_type

        if data is not None:
            self.data = np.asarray(data, dtype=np.float32)
        elif size is not None:
            self.data = np.zeros(size, dtype=np.float32)
        else:
            self.data = np.zeros((100, 100), dtype=np.float32)

        self.name = name or ("Erase" if mode == "erase" else "Add")

    def at(self, shape) -> np.ndarray:
        h, w = shape[:2]
        if self.data.shape[:2] == (h, w):
            return self.data
        return cv2.resize(self.data, (w, h), interpolation=cv2.INTER_LINEAR)

    def copy(self) -> "SubMask":
        return SubMask(
            data=self.data.copy(),
            mode=self.mode,
            mask_type=self.mask_type,
            name=self.name,
        )


class Mask:
    """Main float32 (H, W) mask in [0, 1] with optional child sub-masks."""

    def __init__(self, data=None, size=None):
        if data is not None:
            self.data = np.asarray(data, dtype=np.float32)
        elif size is not None:
            self.data = np.ones(size, dtype=np.float32)
        else:
            self.data = np.ones((100, 100), dtype=np.float32)

        self.sub_masks: list[SubMask] = []

    def at(self, shape) -> np.ndarray:
        h, w = shape[:2]
        if self.data.shape[:2] == (h, w):
            return self.data
        return cv2.resize(self.data, (w, h), interpolation=cv2.INTER_LINEAR)

    def compute_effective(self, shape) -> np.ndarray:
        """Composite main mask with all sub-masks and return final float32 (H, W)."""
        h, w = shape[:2]
        result = self.at((h, w)).copy()
        for sm in self.sub_masks:
            sm_data = sm.at((h, w))
            if sm.mode == "erase":
                result = result * (1.0 - sm_data)
            else:  # paint
                result = result * sm_data
        return np.clip(result, 0.0, 1.0).astype(np.float32)

    def copy(self) -> "Mask":
        new = Mask(data=self.data.copy())
        new.sub_masks = [sm.copy() for sm in self.sub_masks]
        return new

    def add_sub_mask(
        self,
        mode: str = "erase",
        mask_type: str = "brush",
        size=None,
    ) -> SubMask:
        """Create and append a new empty sub-mask."""
        if size is None:
            size = self.data.shape[:2]
        sm = SubMask(size=size, mode=mode, mask_type=mask_type)
        self.sub_masks.append(sm)
        return sm

    # --- In-place operations ---

    def invert(self):
        self.data = np.clip(1.0 - self.data, 0.0, 1.0)
        return self

    def clear(self):
        self.data.fill(0.0)
        return self

    def fill(self):
        self.data.fill(1.0)
        return self

    def feather(self, sigma: float = 5.0):
        if sigma > 0:
            ksize = int(sigma * 4) | 1
            self.data = cv2.GaussianBlur(self.data, (ksize, ksize), sigmaX=sigma)
            self.data = np.clip(self.data, 0.0, 1.0)
        return self

    # --- Mask-type generators ---

    def set_radial_gradient(
        self,
        center,
        radius_x: float,
        radius_y: float,
        feather: float = 0.5,
    ):
        h, w = self.data.shape[:2]
        cx, cy = center
        rx = max(1.0, float(radius_x))
        ry = max(1.0, float(radius_y))
        feather = float(np.clip(feather, 0.01, 0.99))
        y, x = np.ogrid[:h, :w]
        dist = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
        inner = 1.0 - feather
        self.data = np.clip(1.0 - (dist - inner) / feather, 0.0, 1.0).astype(np.float32)
        return self

    def set_linear_gradient(self, start_pt, end_pt):
        h, w = self.data.shape[:2]
        x1, y1 = start_pt
        x2, y2 = end_pt
        dx, dy = x2 - x1, y2 - y1
        len_sq = dx * dx + dy * dy
        y, x = np.ogrid[:h, :w]
        if len_sq < 1e-4:
            self.data = np.ones((h, w), dtype=np.float32)
        else:
            proj = 1.0 - ((x - x1) * dx + (y - y1) * dy) / len_sq
            self.data = np.clip(proj, 0.0, 1.0).astype(np.float32)
        return self

    def set_color_range(
        self,
        image_arr: np.ndarray,
        target_rgb,
        tolerance: float = 0.35,
        feather: float = 0.2,
    ):
        h, w = self.data.shape[:2]
        rgb = image_arr[..., :3].astype(np.float32)
        if rgb.shape[:2] != (h, w):
            rgb = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_LINEAR)
        target = np.array(target_rgb[:3], dtype=np.float32)
        dist = np.linalg.norm(rgb - target, axis=2) / 441.67
        tol = max(0.01, tolerance)
        f = max(0.01, feather)
        self.data = np.clip(
            1.0 - (dist - (tol * (1.0 - f))) / (tol * f), 0.0, 1.0
        ).astype(np.float32)
        return self

    def set_luminance_range(
        self,
        image_arr: np.ndarray,
        min_lum: float = 0.0,
        max_lum: float = 1.0,
        feather: float = 0.15,
    ):
        h, w = self.data.shape[:2]
        rgb = image_arr[..., :3].astype(np.float32)
        if rgb.shape[:2] != (h, w):
            rgb = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_LINEAR)
        lum = (
            0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
        ) / 255.0
        f = max(0.01, feather)
        low = np.clip((lum - (min_lum - f)) / f, 0.0, 1.0)
        high = np.clip(((max_lum + f) - lum) / f, 0.0, 1.0)
        self.data = (low * high).astype(np.float32)
        return self


# ===========================================================================
# Adjustments
# ===========================================================================


class Adjustment:
    name: str = "Adjustment"
    key: str = "adj"
    category: str = "Light"
    min_val: float = -100.0
    max_val: float = 100.0
    default_val: float = 0.0

    def apply(self, arr: np.ndarray, value: float) -> np.ndarray:
        raise NotImplementedError


class Exposure(Adjustment):
    name, key, category = "Exposure", "exposure", "Light"

    def apply(self, arr, value):
        if value == 0:
            return arr
        lut = np.clip(np.arange(256) * (2.0 ** (value / 50.0)), 0, 255).astype(np.uint8)
        out = arr.copy()
        out[..., :3] = cv2.LUT(np.ascontiguousarray(arr[..., :3]), lut)
        return out


class Contrast(Adjustment):
    name, key, category = "Contrast", "contrast", "Light"

    def apply(self, arr, value):
        if value == 0:
            return arr
        v = np.clip(value, -99.0, 99.0)
        factor = (259.0 * (v + 255.0)) / (255.0 * (259.0 - v))
        x = np.arange(256, dtype=np.float32)
        lut = np.clip(128.0 + factor * (x - 128.0), 0, 255).astype(np.uint8)
        out = arr.copy()
        out[..., :3] = cv2.LUT(np.ascontiguousarray(arr[..., :3]), lut)
        return out


class Highlights(Adjustment):
    name, key, category = "Highlights", "highlights", "Light"

    def apply(self, arr, value):
        if value == 0:
            return arr
        x = np.arange(256, dtype=np.float32)
        weight = np.clip((x - 120.0) / 135.0, 0.0, 1.0) ** 1.3
        lut = np.clip(x + value * 0.55 * weight, 0, 255).astype(np.uint8)
        out = arr.copy()
        out[..., :3] = cv2.LUT(np.ascontiguousarray(arr[..., :3]), lut)
        return out


class Shadows(Adjustment):
    name, key, category = "Shadows", "shadows", "Light"

    def apply(self, arr, value):
        if value == 0:
            return arr
        x = np.arange(256, dtype=np.float32)
        weight = np.clip((135.0 - x) / 135.0, 0.0, 1.0) ** 1.3
        lut = np.clip(x + value * 0.55 * weight, 0, 255).astype(np.uint8)
        out = arr.copy()
        out[..., :3] = cv2.LUT(np.ascontiguousarray(arr[..., :3]), lut)
        return out


class Whites(Adjustment):
    name, key, category = "Whites", "whites", "Light"

    def apply(self, arr, value):
        if value == 0:
            return arr
        x = np.arange(256, dtype=np.float32)
        weight = np.clip((x - 160.0) / 95.0, 0.0, 1.0) ** 1.8
        lut = np.clip(x + value * 0.65 * weight, 0, 255).astype(np.uint8)
        out = arr.copy()
        out[..., :3] = cv2.LUT(np.ascontiguousarray(arr[..., :3]), lut)
        return out


class Blacks(Adjustment):
    name, key, category = "Blacks", "blacks", "Light"

    def apply(self, arr, value):
        if value == 0:
            return arr
        x = np.arange(256, dtype=np.float32)
        weight = np.clip((95.0 - x) / 95.0, 0.0, 1.0) ** 1.8
        lut = np.clip(x + value * 0.65 * weight, 0, 255).astype(np.uint8)
        out = arr.copy()
        out[..., :3] = cv2.LUT(np.ascontiguousarray(arr[..., :3]), lut)
        return out


class Temperature(Adjustment):
    name, key, category = "Temp", "temperature", "Color"

    def apply(self, arr, value):
        if value == 0:
            return arr
        x = np.arange(256, dtype=np.float32)
        lut_r = np.clip(x + value * 0.5, 0, 255).astype(np.uint8)
        lut_b = np.clip(x - value * 0.5, 0, 255).astype(np.uint8)
        out = arr.copy()
        out[..., 0] = cv2.LUT(np.ascontiguousarray(arr[..., 0]), lut_r)
        out[..., 2] = cv2.LUT(np.ascontiguousarray(arr[..., 2]), lut_b)
        return out


class Tint(Adjustment):
    name, key, category = "Tint", "tint", "Color"

    def apply(self, arr, value):
        if value == 0:
            return arr
        x = np.arange(256, dtype=np.float32)
        lut_g = np.clip(x - value * 0.45, 0, 255).astype(np.uint8)
        out = arr.copy()
        out[..., 1] = cv2.LUT(np.ascontiguousarray(arr[..., 1]), lut_g)
        return out


class Vibrance(Adjustment):
    name, key, category = "Vibrance", "vibrance", "Color"

    def apply(self, arr, value):
        if value == 0:
            return arr
        rgb = arr[..., :3]
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.float32)
        s = hsv[..., 1] / 255.0
        delta = (value / 100.0) * (1.0 - s) * (1.0 - s * 0.5)
        hsv[..., 1] = np.clip((s + delta) * 255.0, 0, 255)
        out = arr.copy()
        out[..., :3] = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
        return out


class Saturation(Adjustment):
    name, key, category = "Saturation", "saturation", "Color"

    def apply(self, arr, value):
        if value == 0:
            return arr
        rgb = arr[..., :3]
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.float32)
        factor = 1.0 + (value / 100.0)
        hsv[..., 1] = np.clip(hsv[..., 1] * factor, 0, 255)
        out = arr.copy()
        out[..., :3] = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
        return out


class Hue(Adjustment):
    name, key, category = "Hue", "hue", "Color"

    def apply(self, arr, value):
        if value == 0:
            return arr
        rgb = arr[..., :3]
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.float32)
        shift = (value / 100.0) * 90.0
        hsv[..., 0] = (hsv[..., 0] + shift) % 180.0
        out = arr.copy()
        out[..., :3] = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
        return out


class Clarity(Adjustment):
    name, key, category = "Clarity", "clarity", "Effects"

    def apply(self, arr, value):
        if value == 0:
            return arr
        rgb = arr[..., :3]
        blur = cv2.GaussianBlur(rgb, (0, 0), sigmaX=3.0)
        diff = rgb.astype(np.float32) - blur.astype(np.float32)
        scaled = rgb.astype(np.float32) + diff * (value / 100.0) * 1.4
        out = arr.copy()
        out[..., :3] = np.clip(scaled, 0, 255).astype(np.uint8)
        return out


class Vignette(Adjustment):
    name, key, category = "Vignette", "vignette", "Effects"

    def apply(self, arr, value):
        if value == 0:
            return arr
        h, w = arr.shape[:2]
        y, x = np.ogrid[:h, :w]
        cx, cy = w / 2.0, h / 2.0
        dist = np.sqrt(((x - cx) / cx) ** 2 + ((y - cy) / cy) ** 2)
        mask = np.clip((dist - 0.4) / 0.8, 0.0, 1.0)
        factor = 1.0 + (value / 100.0) * mask[..., None]
        rgb = np.clip(arr[..., :3].astype(np.float32) * factor, 0, 255).astype(np.uint8)
        out = arr.copy()
        out[..., :3] = rgb
        return out


class Sharpen(Adjustment):
    name, key, category = "Sharpen", "sharpen", "Effects"

    def apply(self, arr, value):
        if value == 0:
            return arr
        rgb = arr[..., :3]
        if value > 0:
            blurred = cv2.GaussianBlur(rgb, (0, 0), sigmaX=1.0)
            amount = (value / 100.0) * 1.5
            sharp = cv2.addWeighted(rgb, 1.0 + amount, blurred, -amount, 0)
        else:
            sigma = (-value / 100.0) * 2.5
            sharp = cv2.GaussianBlur(rgb, (0, 0), sigmaX=max(0.5, sigma))
        out = arr.copy()
        out[..., :3] = sharp
        return out


ADJUSTMENTS_LIST = [
    Exposure(),
    Contrast(),
    Highlights(),
    Shadows(),
    Whites(),
    Blacks(),
    Temperature(),
    Tint(),
    Vibrance(),
    Saturation(),
    Hue(),
    Clarity(),
    Vignette(),
    Sharpen(),
]

ADJUSTMENTS_MAP: dict[str, Adjustment] = {adj.key: adj for adj in ADJUSTMENTS_LIST}
CATEGORIES = ["Light", "Color", "Effects"]
ADJUSTMENTS_BY_CATEGORY: dict[str, list[Adjustment]] = {
    cat: [adj for adj in ADJUSTMENTS_LIST if adj.category == cat]
    for cat in CATEGORIES
}


# ===========================================================================
# Layer
# ===========================================================================


class Layer:
    def __init__(
        self,
        adjustments=None,
        mask: Mask | None = None,
        name: str = "Layer",
        mask_type: str = "global",
        visible: bool = True,
        opacity: float = 1.0,
        inverted: bool = False,
    ):
        self.id = uuid.uuid4().hex[:8]
        self.name = name
        self.mask_type = mask_type
        self.mask = mask
        self.visible = visible
        self.opacity = float(opacity)
        self.inverted = bool(inverted)

        self.values: dict[str, float] = {adj.key: adj.default_val for adj in ADJUSTMENTS_LIST}

        if adjustments:
            for item in adjustments:
                if isinstance(item, Adjustment):
                    self.values[item.key] = item.default_val

    def get_effective_mask(self, shape) -> np.ndarray:
        """Compute final composited mask (H, W) applying sub-masks + invert + opacity."""
        if self.mask is None:
            m = np.ones(shape[:2], dtype=np.float32)
        else:
            m = self.mask.compute_effective(shape[:2])
            if self.inverted:
                m = 1.0 - m
        if self.opacity != 1.0:
            m = m * self.opacity
        return np.clip(m, 0.0, 1.0)

    def has_adjustments(self) -> bool:
        return any(v != 0.0 for v in self.values.values())

    def reset_adjustments(self):
        for k in self.values:
            self.values[k] = 0.0

    def apply(self, arr: np.ndarray) -> np.ndarray:
        if not self.visible or not self.has_adjustments():
            return arr

        out = arr
        for adj in ADJUSTMENTS_LIST:
            val = self.values.get(adj.key, 0.0)
            if val != 0.0:
                out = adj.apply(out, val)

        if out is arr:
            return arr

        m = self.get_effective_mask(arr.shape[:2])[..., None]
        base = arr.astype(np.float32)
        edited = out.astype(np.float32)
        blended = base * (1.0 - m) + edited * m
        return np.clip(blended, 0, 255).astype(np.uint8)
