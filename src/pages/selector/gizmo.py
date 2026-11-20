import cv2
import numpy as np

# Color constants
C_WHITE = (255, 255, 255)
C_BLACK = (15, 15, 15)
C_ACCENT = (0, 165, 255)  # Orange accent for active/selected handles


def _draw_dashed_line(
    img: np.ndarray,
    pt1: tuple[float, float],
    pt2: tuple[float, float],
    color: tuple[int, int, int],
    thickness: int = 1,
    dash_len: int = 8,
    gap_len: int = 6,
) -> None:
    """Draw an anti-aliased dashed line between pt1 and pt2."""
    p1 = np.array(pt1, dtype=np.float32)
    p2 = np.array(pt2, dtype=np.float32)
    dist = float(np.linalg.norm(p2 - p1))
    if dist < 1.0:
        return
    step = float(dash_len + gap_len)
    num = max(1, int(dist / step))
    u = (p2 - p1) / dist
    for i in range(num):
        s = p1 + u * (i * step)
        e = p1 + u * min(dist, i * step + dash_len)
        cv2.line(
            img,
            (int(round(s[0])), int(round(s[1]))),
            (int(round(e[0])), int(round(e[1]))),
            color,
            thickness,
            cv2.LINE_AA,
        )


def _draw_dashed_ellipse(
    img: np.ndarray,
    center: tuple[float, float],
    axes: tuple[float, float],
    angle: float,
    color: tuple[int, int, int],
    thickness: int = 1,
    step_deg: int = 14,
) -> None:
    """Draw a dashed ellipse using smooth arc segments."""
    c_int = (int(round(center[0])), int(round(center[1])))
    ax_int = (max(1, int(round(axes[0]))), max(1, int(round(axes[1]))))
    for a in range(0, 360, step_deg):
        if (a // step_deg) % 2 == 0:
            continue
        cv2.ellipse(
            img,
            c_int,
            ax_int,
            angle,
            a,
            min(360, a + int(step_deg * 0.6)),
            color,
            thickness,
            cv2.LINE_AA,
        )


def _draw_handle(
    img: np.ndarray,
    pt: tuple[float, float],
    radius: int = 5,
    is_active: bool = False,
) -> None:
    """Draw a Lightroom-style circular control handle."""
    x, y = int(round(pt[0])), int(round(pt[1]))
    cv2.circle(img, (x, y), radius + 2, C_BLACK, -1, cv2.LINE_AA)
    fill_col = C_ACCENT if is_active else C_WHITE
    cv2.circle(img, (x, y), radius, fill_col, -1, cv2.LINE_AA)
    cv2.circle(img, (x, y), max(1, radius - 3), C_BLACK, -1, cv2.LINE_AA)


def _draw_pin(
    img: np.ndarray,
    pt: tuple[float, float],
    is_active: bool = False,
) -> None:
    """Draw the Lightroom center anchor pin."""
    x, y = int(round(pt[0])), int(round(pt[1]))
    cv2.circle(img, (x, y), 8, C_BLACK, -1, cv2.LINE_AA)
    cv2.circle(img, (x, y), 6, C_ACCENT if is_active else C_WHITE, -1, cv2.LINE_AA)
    cv2.circle(img, (x, y), 2, C_BLACK, -1, cv2.LINE_AA)


# =============================================================================
# Radial Gradient Gizmo
# =============================================================================


def get_radial_handle_positions(
    cx: float, cy: float, rx: float, ry: float, deg: float, feather: float
) -> dict:
    rad = np.radians(deg)
    cos_a, sin_a = float(np.cos(rad)), float(np.sin(rad))

    pt_right = (cx + rx * cos_a, cy + rx * sin_a)
    pt_left = (cx - rx * cos_a, cy - rx * sin_a)
    pt_bottom = (cx - ry * sin_a, cy + ry * cos_a)
    pt_top = (cx + ry * sin_a, cy - ry * cos_a)

    rot_dist = rx + 24.0
    pt_rot = (cx + rot_dist * cos_a, cy + rot_dist * sin_a)

    inner_ry = ry * max(0.01, 1.0 - feather)
    pt_fth = (cx + inner_ry * sin_a, cy - inner_ry * cos_a)

    return {
        "center": (cx, cy),
        "right": pt_right,
        "left": pt_left,
        "bottom": pt_bottom,
        "top": pt_top,
        "rot": pt_rot,
        "feather": pt_fth,
    }


def draw_radial_gizmo(img: np.ndarray, state: dict) -> None:
    cx = float(state["rad_cx"])
    cy = float(state["rad_cy"])
    rx = float(state["rad_width"])
    ry = float(state["rad_height"])
    deg = float(state["rad_rot"])
    feather = float(state["rad_feather"])
    hnds = get_radial_handle_positions(cx, cy, rx, ry, deg, feather)

    c_int = (int(round(cx)), int(round(cy)))
    axes_int = (max(1, int(round(rx))), max(1, int(round(ry))))

    # 1. Subtle drop shadow for outer boundary ellipse
    cv2.ellipse(img, c_int, axes_int, deg, 0, 360, C_BLACK, 3, cv2.LINE_AA)
    # 2. Outer boundary ellipse (solid white)
    cv2.ellipse(img, c_int, axes_int, deg, 0, 360, C_WHITE, 1, cv2.LINE_AA)

    # 3. Inner feather boundary (dashed ellipse)
    inner_rx = rx * max(0.01, 1.0 - feather)
    inner_ry = ry * max(0.01, 1.0 - feather)
    _draw_dashed_ellipse(
        img, (cx, cy), (inner_rx, inner_ry), deg, (210, 210, 210), thickness=1
    )

    # 4. Rotation stalk
    cv2.line(
        img,
        (int(round(hnds["right"][0])), int(round(hnds["right"][1]))),
        (int(round(hnds["rot"][0])), int(round(hnds["rot"][1]))),
        C_BLACK,
        3,
        cv2.LINE_AA,
    )
    cv2.line(
        img,
        (int(round(hnds["right"][0])), int(round(hnds["right"][1]))),
        (int(round(hnds["rot"][0])), int(round(hnds["rot"][1]))),
        C_WHITE,
        1,
        cv2.LINE_AA,
    )

    # 5. Control handles
    _draw_handle(img, hnds["right"], radius=5)
    _draw_handle(img, hnds["left"], radius=5)
    _draw_handle(img, hnds["top"], radius=5)
    _draw_handle(img, hnds["bottom"], radius=5)
    _draw_handle(img, hnds["rot"], radius=4)
    _draw_handle(img, hnds["feather"], radius=4)

    # 6. Center Pin
    _draw_pin(img, hnds["center"])


def hit_test_radial(tx: float, ty: float, state: dict) -> str:
    cx = float(state["rad_cx"])
    cy = float(state["rad_cy"])
    rx = float(state["rad_width"])
    ry = float(state["rad_height"])
    deg = float(state["rad_rot"])
    feather = float(state["rad_feather"])
    hnds = get_radial_handle_positions(cx, cy, rx, ry, deg, feather)

    # 1. Center pin
    if np.hypot(tx - cx, ty - cy) <= 18:
        return "move"

    # 2. Rotation handle
    if np.hypot(tx - hnds["rot"][0], ty - hnds["rot"][1]) <= 18:
        return "rotate"

    # 3. Width handles (Right / Left)
    if (
        np.hypot(tx - hnds["right"][0], ty - hnds["right"][1]) <= 18
        or np.hypot(tx - hnds["left"][0], ty - hnds["left"][1]) <= 18
    ):
        return "resize_w"

    # 4. Height handles (Top / Bottom)
    if (
        np.hypot(tx - hnds["top"][0], ty - hnds["top"][1]) <= 18
        or np.hypot(tx - hnds["bottom"][0], ty - hnds["bottom"][1]) <= 18
    ):
        return "resize_h"

    # 5. Feather handle
    if np.hypot(tx - hnds["feather"][0], ty - hnds["feather"][1]) <= 16:
        return "feather"

    # 6. Near boundary ellipse
    rad = np.radians(deg)
    dx = tx - cx
    dy = ty - cy
    xr = dx * np.cos(rad) + dy * np.sin(rad)
    yr = -dx * np.sin(rad) + dy * np.cos(rad)
    dist_norm = np.sqrt((xr / max(1.0, rx)) ** 2 + (yr / max(1.0, ry)) ** 2)
    if abs(dist_norm - 1.0) < 0.15:
        return "resize_both"

    return "create"


def update_radial_drag(
    mode: str,
    ix: float,
    iy: float,
    start_pt: tuple[float, float],
    state: dict,
    prev_w: int,
    prev_h: int,
) -> None:
    sx, sy = start_pt
    if mode == "create":
        dx = ix - sx
        dy = iy - sy
        dist = float(np.hypot(dx, dy))
        state["rad_cx"] = float(sx)
        state["rad_cy"] = float(sy)
        state["rad_width"] = max(15.0, dist)
        state["rad_height"] = max(15.0, dist * 0.75)
        if dist > 8.0:
            state["rad_rot"] = float(np.degrees(np.arctan2(dy, dx)))
    elif mode == "move":
        dx = ix - sx
        dy = iy - sy
        state["rad_cx"] = float(state["rad_cx"] + dx)
        state["rad_cy"] = float(state["rad_cy"] + dy)
    elif mode == "rotate":
        cx = float(state["rad_cx"])
        cy = float(state["rad_cy"])
        state["rad_rot"] = float(np.degrees(np.arctan2(iy - cy, ix - cx)))
    elif mode == "resize_w":
        cx = float(state["rad_cx"])
        cy = float(state["rad_cy"])
        rad = np.radians(state["rad_rot"])
        dx = ix - cx
        dy = iy - cy
        xr = dx * np.cos(rad) + dy * np.sin(rad)
        state["rad_width"] = max(10.0, float(abs(xr)))
    elif mode == "resize_h":
        cx = float(state["rad_cx"])
        cy = float(state["rad_cy"])
        rad = np.radians(state["rad_rot"])
        dx = ix - cx
        dy = iy - cy
        yr = -dx * np.sin(rad) + dy * np.cos(rad)
        state["rad_height"] = max(10.0, float(abs(yr)))
    elif mode == "resize_both":
        cx = float(state["rad_cx"])
        cy = float(state["rad_cy"])
        dist = float(np.hypot(ix - cx, iy - cy))
        ratio = state["rad_height"] / max(1.0, state["rad_width"])
        state["rad_width"] = max(15.0, dist)
        state["rad_height"] = max(15.0, dist * ratio)
    elif mode == "feather":
        cx = float(state["rad_cx"])
        cy = float(state["rad_cy"])
        dist = float(np.hypot(ix - cx, iy - cy))
        state["rad_feather"] = float(
            np.clip(1.0 - dist / max(1.0, state["rad_height"]), 0.05, 0.95)
        )


# =============================================================================
# Linear Gradient Gizmo
# =============================================================================


def get_linear_handle_positions(
    cx: float, cy: float, span: float, deg: float, w: int, h: int
) -> dict:
    rad = np.radians(deg)
    ux, uy = float(np.cos(rad)), float(np.sin(rad))
    vx, vy = -uy, ux

    half_span = span / 2.0
    half_line = max(span * 0.75, min(w, h) * 0.35, 75.0)

    # Mid line endpoints
    mid_start = (cx - half_line * vx, cy - half_line * vy)
    mid_end = (cx + half_line * vx, cy + half_line * vy)

    # Start line (100% boundary) center & endpoints
    scx, scy = cx - half_span * ux, cy - half_span * uy
    s_start = (scx - half_line * vx, scy - half_line * vy)
    s_end = (scx + half_line * vx, scy + half_line * vy)

    # End line (0% boundary) center & endpoints
    ecx, ecy = cx + half_span * ux, cy + half_span * uy
    e_start = (ecx - half_line * vx, ecy - half_line * vy)
    e_end = (ecx + half_line * vx, ecy + half_line * vy)

    # Rotate tip
    tip_dist = half_span + 24.0
    rot_tip = (cx + tip_dist * ux, cy + tip_dist * uy)

    return {
        "center": (cx, cy),
        "start_c": (scx, scy),
        "end_c": (ecx, ecy),
        "mid_p1": mid_start,
        "mid_p2": mid_end,
        "start_p1": s_start,
        "start_p2": s_end,
        "end_p1": e_start,
        "end_p2": e_end,
        "rot": rot_tip,
    }


def draw_linear_gizmo(img: np.ndarray, state: dict, w: int, h: int) -> None:
    cx = float(state["lin_cx"])
    cy = float(state["lin_cy"])
    span = float(state.get("lin_span", min(w, h) * 0.4))
    deg = float(state["lin_deg"])
    hnds = get_linear_handle_positions(cx, cy, span, deg, w, h)

    # 1. Gradient axis normal line (start_c to end_c, extending to rot tip)
    cv2.line(
        img,
        (int(round(hnds["start_c"][0])), int(round(hnds["start_c"][1]))),
        (int(round(hnds["rot"][0])), int(round(hnds["rot"][1]))),
        C_BLACK,
        3,
        cv2.LINE_AA,
    )
    cv2.line(
        img,
        (int(round(hnds["start_c"][0])), int(round(hnds["start_c"][1]))),
        (int(round(hnds["rot"][0])), int(round(hnds["rot"][1]))),
        C_WHITE,
        1,
        cv2.LINE_AA,
    )

    # 2. Start line (100% boundary, dashed)
    _draw_dashed_line(img, hnds["start_p1"], hnds["start_p2"], C_WHITE, thickness=1)

    # 3. Center line (50% midpoint, solid white line with black drop shadow)
    cv2.line(
        img,
        (int(round(hnds["mid_p1"][0])), int(round(hnds["mid_p1"][1]))),
        (int(round(hnds["mid_p2"][0])), int(round(hnds["mid_p2"][1]))),
        C_BLACK,
        3,
        cv2.LINE_AA,
    )
    cv2.line(
        img,
        (int(round(hnds["mid_p1"][0])), int(round(hnds["mid_p1"][1]))),
        (int(round(hnds["mid_p2"][0])), int(round(hnds["mid_p2"][1]))),
        C_WHITE,
        1,
        cv2.LINE_AA,
    )

    # 4. End line (0% boundary, dashed)
    _draw_dashed_line(img, hnds["end_p1"], hnds["end_p2"], C_WHITE, thickness=1)

    # 5. Handles on start and end centers
    _draw_handle(img, hnds["start_c"], radius=5)
    _draw_handle(img, hnds["end_c"], radius=5)

    # 6. Rotate handle at axis tip
    _draw_handle(img, hnds["rot"], radius=4)

    # 7. Center Pin
    _draw_pin(img, hnds["center"])


def hit_test_linear(tx: float, ty: float, state: dict, w: int, h: int) -> str:
    cx = float(state["lin_cx"])
    cy = float(state["lin_cy"])
    span = float(state.get("lin_span", min(w, h) * 0.4))
    deg = float(state["lin_deg"])
    hnds = get_linear_handle_positions(cx, cy, span, deg, w, h)

    # 1. Center pin
    if np.hypot(tx - cx, ty - cy) <= 18:
        return "move"

    # 2. Rotate tip
    if np.hypot(tx - hnds["rot"][0], ty - hnds["rot"][1]) <= 18:
        return "rotate"

    # 3. Start / End handles
    if (
        np.hypot(tx - hnds["start_c"][0], ty - hnds["start_c"][1]) <= 18
        or np.hypot(tx - hnds["end_c"][0], ty - hnds["end_c"][1]) <= 18
    ):
        return "resize_span"

    # 4. Near start line or end line
    rad = np.radians(deg)
    ux, uy = float(np.cos(rad)), float(np.sin(rad))
    p = (tx - cx) * ux + (ty - cy) * uy
    half_span = span / 2.0
    if abs(abs(p) - half_span) <= 15:
        return "resize_span"

    # 5. Near center line
    if abs(p) <= 15:
        return "move"

    return "create"


def update_linear_drag(
    mode: str,
    ix: float,
    iy: float,
    start_pt: tuple[float, float],
    state: dict,
    prev_w: int,
    prev_h: int,
) -> None:
    sx, sy = start_pt
    if mode == "create":
        dx = ix - sx
        dy = iy - sy
        dist = float(np.hypot(dx, dy))
        state["lin_cx"] = float((sx + ix) / 2.0)
        state["lin_cy"] = float((sy + iy) / 2.0)
        state["lin_span"] = max(15.0, dist)
        if dist > 8.0:
            state["lin_deg"] = float(np.degrees(np.arctan2(dy, dx)))
    elif mode == "move":
        dx = ix - sx
        dy = iy - sy
        state["lin_cx"] = float(state["lin_cx"] + dx)
        state["lin_cy"] = float(state["lin_cy"] + dy)
    elif mode == "rotate":
        cx = float(state["lin_cx"])
        cy = float(state["lin_cy"])
        state["lin_deg"] = float(np.degrees(np.arctan2(iy - cy, ix - cx)))
    elif mode == "resize_span":
        cx = float(state["lin_cx"])
        cy = float(state["lin_cy"])
        rad = np.radians(state["lin_deg"])
        ux, uy = float(np.cos(rad)), float(np.sin(rad))
        p = (ix - cx) * ux + (iy - cy) * uy
        state["lin_span"] = max(15.0, float(abs(p) * 2.0))
