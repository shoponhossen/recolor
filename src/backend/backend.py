import numpy as np, cv2


class Mask:
    """Float32 (H, W), 0..1. Stored once at full-res, resampled on demand."""

    def __init__(self, data=None, size=None):
        self.data = data if data is not None else np.ones(size, np.float32)

    def at(self, shape):
        h, w = shape[:2]
        if self.data.shape == (h, w):
            return self.data
        return cv2.resize(self.data, (w, h), interpolation=cv2.INTER_LINEAR)


class Adjustment:
    min, max, default = -100, 100, 0

    def apply(self, arr, value):
        raise NotImplementedError


class Exposure(Adjustment):
    def apply(self, arr, value):
        lut = np.clip(np.arange(256) * 2 ** (value / 50), 0, 255).astype(np.uint8)
        out = arr.copy()
        out[..., :3] = cv2.LUT(
            np.ascontiguousarray(arr[..., :3]), lut
        )  # alpha untouched
        return out


class Layer:
    def __init__(self, adjs, mask=None):
        self.mask, self.visible = mask, True
        self.values = {
            a: a.default for a in adjs
        }  # dict keeps insertion order, so this is the apply order

    def apply(self, arr):
        if not self.visible:
            return arr
        out = arr
        for adj, v in self.values.items():
            if v != adj.default:
                out = adj.apply(out, v)
        if out is arr or self.mask is None:
            return out
        m = self.mask.at(arr.shape)[..., None]
        a = arr.astype(np.float32)
        return (a + (out - a) * m).astype(np.uint8)
