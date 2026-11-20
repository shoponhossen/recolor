import numpy as np
import cv2
from utils import arr_to_jpeg_bytes, create_mask_overlay
from .constants import MAIN_COLOR, ERASE_COLOR, PAINT_COLOR
from .helpers import safe_at


def render_mask_canvas(
    project,
    state: dict,
    im_buf: np.ndarray,
    fast_im_buf: np.ndarray,
    prev_arr: np.ndarray,
    fast_prev_arr: np.ndarray,
    prev_w: int,
    prev_h: int,
    fast_w: int,
    fast_h: int,
    fast: bool = False,
) -> bytes:
    """
    Compose rubylith overlay using either low-res fast buffer or full preview buffer.
    Always outputs at (prev_w, prev_h) so canvas image and containers never shrink.
    """
    mi = state["main_idx"]
    si = state["sub_idx"]
    layer = project.layers[mi]

    if fast:
        target_buf = fast_im_buf
        base_img = fast_prev_arr
        ch, cw = fast_h, fast_w
        jpeg_q = 65
    else:
        target_buf = im_buf
        base_img = prev_arr
        ch, cw = prev_h, prev_w
        jpeg_q = 80

    if si == -1:
        main_data = target_buf
    else:
        main_data = safe_at(layer.mask, ch, cw)

    result = main_data.copy()
    for s_i, sm in enumerate(layer.mask.sub_masks):
        sm_data = target_buf if s_i == si else safe_at(sm, ch, cw)
        if sm.mode == "erase":
            result = result * (1.0 - sm_data)
        else:
            result = result * sm_data
    result = np.clip(result, 0.0, 1.0)

    # Main rubylith (red)
    overlay = create_mask_overlay(base_img, result, color=MAIN_COLOR, opacity=0.52)

    # If editing a sub-mask, additionally highlight it in blue/green
    if 0 <= si < len(layer.mask.sub_masks):
        sm = layer.mask.sub_masks[si]
        tint = ERASE_COLOR if sm.mode == "erase" else PAINT_COLOR
        overlay = create_mask_overlay(overlay, target_buf, color=tint, opacity=0.35)

    # Upscale back to (prev_w, prev_h) during fast preview so layout stays stable
    if fast and (cw != prev_w or ch != prev_h):
        overlay = cv2.resize(overlay, (prev_w, prev_h), interpolation=cv2.INTER_NEAREST)

    return arr_to_jpeg_bytes(overlay, quality=jpeg_q)
