"""
Mask Studio — selector_view
Layout:
  AppBar
  Stack(expand) [
    GestureDetector(image, full area)
    MaskListPanel (right=0, overlay, semi-transparent)
  ]
  ToolOptionsBar
  ToolBar
"""

import flet as ft
from app import ReColor
from utils import arr_to_jpeg_bytes, create_mask_overlay
from backend.backend import Layer, Mask, SubMask
import numpy as np
import cv2


# ---- Colour constants for sub-mask modes ----
ERASE_COLOR = (60, 100, 255)   # blue tint for erase sub-masks
PAINT_COLOR = (50, 200, 100)   # green tint for paint sub-masks
MAIN_COLOR  = (255, 45, 45)    # red rubylith for main/effective


def selector_view(page: ft.Page, app: ReColor) -> ft.View:
    page.overlay.clear()
    pm = app.projects_manager

    if pm.project is None:
        pm.create_project("Default", r"D:\Projects\recolor\default.jpg")

    project = pm.project

    # Resolve initial active layer
    if app.active_mask_layer and app.active_mask_layer in project.layers:
        init_layer = app.active_mask_layer
    elif project.selected_layer and project.selected_layer in project.layers:
        init_layer = project.selected_layer
    else:
        if not project.layers:
            project.add_layer("Global", "global")
        init_layer = project.layers[0]

    prev_arr = project.preview_image_array
    prev_h, prev_w = prev_arr.shape[:2]

    # ===========================================================
    # Mutable editing state (using list/dict for closure mutation)
    # ===========================================================
    state = {
        "main_idx": project.layers.index(init_layer),
        "sub_idx":  -1,          # -1 = editing main mask, >=0 = sub-mask
        "tool":     "brush",     # brush | eraser | radial | linear | color
        "brush_sz": 25.0,
        "feather":  0.3,
        "rad_cx":   prev_w / 2.0,
        "rad_cy":   prev_h / 2.0,
        "rad_rx":   prev_w * 0.35,
        "rad_ry":   prev_h * 0.35,
        "rad_fth":  0.5,
        "col_rgb":  None,         # sampled color (R,G,B) for color-range
        "col_tol":  0.35,
        "lin_dir":  "top",        # top | bottom | left | right
    }

    # Canvas viewport tracking (updated via on_size_change)
    viewport = [360.0, 420.0]

    # Working mask buffer at preview resolution
    im_buf: np.ndarray = _load_target_buf(project, state["main_idx"], state["sub_idx"],
                                          prev_h, prev_w)

    stroke: list[tuple[float, float]] = []

    # ============================================================
    # Coordinate mapping
    # ============================================================
    def to_img(x: float, y: float):
        vw, vh = viewport[0], viewport[1]
        scale = min(vw / prev_w, vh / prev_h)
        rw, rh = prev_w * scale, prev_h * scale
        ox = (vw - rw) / 2.0
        oy = (vh - rh) / 2.0
        ix = (x - ox) / scale
        iy = (y - oy) / scale
        return (
            max(0.0, min(prev_w - 1.0, ix)),
            max(0.0, min(prev_h - 1.0, iy)),
        )

    # ============================================================
    # Overlay renderer
    # ============================================================
    def render_canvas() -> bytes:
        """Compose rubylith overlay using current im_buf (live edit buffer)."""
        mi = state["main_idx"]
        si = state["sub_idx"]
        layer = project.layers[mi]

        if si == -1:
            # Editing the main mask: use im_buf as main
            main_data = im_buf
        else:
            main_data = _safe_at(layer.mask, prev_h, prev_w)

        result = main_data.copy()
        for s_i, sm in enumerate(layer.mask.sub_masks):
            sm_data = im_buf if s_i == si else _safe_at(sm, prev_h, prev_w)
            if sm.mode == "erase":
                result = result * (1.0 - sm_data)
            else:
                result = result * sm_data
        result = np.clip(result, 0.0, 1.0)

        # Main rubylith (red)
        overlay = create_mask_overlay(prev_arr, result, color=MAIN_COLOR, opacity=0.52)

        # If editing a sub-mask, additionally highlight it in blue/green
        if si >= 0 and si < len(layer.mask.sub_masks):
            sm = layer.mask.sub_masks[si]
            tint = ERASE_COLOR if sm.mode == "erase" else PAINT_COLOR
            overlay = create_mask_overlay(overlay, im_buf, color=tint, opacity=0.35)

        return arr_to_jpeg_bytes(overlay, quality=80)

    # ============================================================
    # Canvas Image + GestureDetector
    # ============================================================
    img_disp = ft.Image(
        src=render_canvas(),
        fit=ft.BoxFit.CONTAIN,
        expand=True,
        gapless_playback=True,
    )

    def refresh_canvas():
        img_disp.src = render_canvas()
        try:
            img_disp.update()
        except Exception:
            pass

    def on_canvas_size(e):
        viewport[0] = float(e.width or 360)
        viewport[1] = float(e.height or 420)

    # --- Brush / Eraser painting ---
    def on_pan_start(e: ft.DragStartEvent):
        if state["tool"] not in ("brush", "eraser"):
            return
        stroke.clear()
        ix, iy = to_img(e.local_position.x, e.local_position.y)
        stroke.append((ix, iy))
        color = 0.0 if state["tool"] == "eraser" else 1.0
        r = max(1, int(round(state["brush_sz"] / 2.0)))
        cv2.circle(im_buf, (int(round(ix)), int(round(iy))), r, color, -1, cv2.LINE_AA)
        refresh_canvas()

    def on_pan_update(e: ft.DragUpdateEvent):
        if state["tool"] not in ("brush", "eraser"):
            return
        ix, iy = to_img(e.local_position.x, e.local_position.y)
        color = 0.0 if state["tool"] == "eraser" else 1.0
        r = max(1, int(round(state["brush_sz"] / 2.0)))
        thick = max(1, int(round(state["brush_sz"])))

        if stroke:
            px, py = stroke[-1]
            cv2.line(im_buf,
                     (int(round(px)), int(round(py))),
                     (int(round(ix)), int(round(iy))),
                     color, thick, cv2.LINE_AA)
        cv2.circle(im_buf, (int(round(ix)), int(round(iy))), r, color, -1, cv2.LINE_AA)
        stroke.append((ix, iy))
        refresh_canvas()

    def on_pan_end(e: ft.DragEndEvent):
        stroke.clear()
        if state["tool"] in ("brush", "eraser"):
            _apply_feather(im_buf, state["brush_sz"], state["feather"])
            refresh_canvas()

    def on_tap_up(e: ft.TapEvent):
        ix, iy = to_img(e.local_position.x, e.local_position.y)
        px, py = int(round(ix)), int(round(iy))

        if state["tool"] == "color":
            # Sample color from preview and apply color-range mask
            rgb = tuple(int(c) for c in prev_arr[py, px][:3])
            state["col_rgb"] = rgb
            apply_color_range()

        elif state["tool"] == "radial":
            state["rad_cx"] = ix
            state["rad_cy"] = iy
            apply_radial()

    gesture_canvas = ft.GestureDetector(
        content=ft.Container(
            content=img_disp,
            expand=True,
            on_size_change=on_canvas_size,
            size_change_interval=50,
        ),
        on_pan_start=on_pan_start,
        on_pan_update=on_pan_update,
        on_pan_end=on_pan_end,
        on_tap_up=on_tap_up,
        drag_interval=16,
        expand=True,
    )

    # ============================================================
    # Mask-type generators that write directly into im_buf
    # ============================================================
    def apply_radial():
        cx, cy = state["rad_cx"], state["rad_cy"]
        rx, ry = state["rad_rx"], state["rad_ry"]
        fth = max(0.01, state["rad_fth"])
        y, x = np.ogrid[:prev_h, :prev_w]
        dist = np.sqrt(((x - cx) / max(1, rx)) ** 2 + ((y - cy) / max(1, ry)) ** 2)
        inner = 1.0 - fth
        np.copyto(im_buf, np.clip(1.0 - (dist - inner) / fth, 0.0, 1.0).astype(np.float32))
        refresh_canvas()

    def apply_linear():
        h, w = prev_h, prev_w
        d = state["lin_dir"]
        y, x = np.ogrid[:h, :w]
        if d == "top":
            grad = np.clip(1.0 - y / max(1, h * 0.65), 0.0, 1.0)
        elif d == "bottom":
            grad = np.clip(1.0 - (h - y) / max(1, h * 0.65), 0.0, 1.0)
        elif d == "left":
            grad = np.clip(1.0 - x / max(1, w * 0.65), 0.0, 1.0)
        else:  # right
            grad = np.clip(1.0 - (w - x) / max(1, w * 0.65), 0.0, 1.0)
        np.copyto(im_buf, grad.astype(np.float32) * np.ones((h, w), dtype=np.float32))
        refresh_canvas()

    def apply_color_range():
        if state["col_rgb"] is None:
            return
        rgb = prev_arr[..., :3].astype(np.float32)
        target = np.array(state["col_rgb"], dtype=np.float32)
        dist = np.linalg.norm(rgb - target, axis=2) / 441.67
        tol = max(0.01, state["col_tol"])
        f = 0.2
        new = np.clip(1.0 - (dist - tol * (1.0 - f)) / (tol * f), 0.0, 1.0).astype(np.float32)
        np.copyto(im_buf, new)
        refresh_canvas()

    # ============================================================
    # Mask-list panel (overlaid right side)
    # ============================================================
    mask_list_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO)

    def rebuild_mask_list():
        mask_list_col.controls.clear()

        # [+] Add new main mask layer button
        mask_list_col.controls.append(
            ft.Container(
                content=ft.Icon(ft.Icons.ADD, size=18, color=ft.Colors.ORANGE_ACCENT_400),
                width=76, height=34,
                bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.ORANGE_ACCENT_400),
                border=ft.Border.all(1, ft.Colors.ORANGE_ACCENT_400),
                border_radius=ft.BorderRadius.all(10),
                alignment=ft.Alignment.CENTER,
                tooltip="New Mask Layer",
                on_click=lambda ev: on_add_main_mask(),
            )
        )

        for li, layer in enumerate(project.layers):
            is_active_layer = li == state["main_idx"]
            is_main_active  = is_active_layer and state["sub_idx"] == -1
            mi = get_mask_icon(layer.mask_type)

            # Layer card
            layer_card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(mi, size=13,
                                color=ft.Colors.ORANGE_ACCENT_400 if is_active_layer else ft.Colors.WHITE_38),
                        ft.Text(layer.name, size=10,
                                color=ft.Colors.WHITE if is_active_layer else ft.Colors.WHITE_60,
                                weight=ft.FontWeight.BOLD if is_main_active else ft.FontWeight.NORMAL,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True),
                    ], spacing=3),
                    ft.Row([
                        # Erase sub-mask add
                        ft.Container(
                            content=ft.Icon(ft.Icons.REMOVE, size=11, color=ft.Colors.RED_400),
                            width=26, height=22,
                            bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.RED_400),
                            border_radius=ft.BorderRadius.all(5),
                            alignment=ft.Alignment.CENTER,
                            tooltip="Add Erase sub-mask",
                            on_click=lambda ev, l=li: on_add_sub(l, "erase"),
                        ),
                        # Paint sub-mask add
                        ft.Container(
                            content=ft.Icon(ft.Icons.ADD, size=11, color=ft.Colors.GREEN_ACCENT_400),
                            width=26, height=22,
                            bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.GREEN_ACCENT_400),
                            border_radius=ft.BorderRadius.all(5),
                            alignment=ft.Alignment.CENTER,
                            tooltip="Add Paint sub-mask",
                            on_click=lambda ev, l=li: on_add_sub(l, "paint"),
                        ),
                        ft.Container(expand=True),
                        # Visibility
                        ft.Container(
                            content=ft.Icon(
                                ft.Icons.VISIBILITY if layer.visible else ft.Icons.VISIBILITY_OFF,
                                size=11,
                                color=ft.Colors.WHITE_60 if layer.visible else ft.Colors.WHITE_24,
                            ),
                            width=22, height=22,
                            on_click=lambda ev, l=layer: toggle_vis(l),
                        ),
                    ], spacing=2),
                ], spacing=3),
                padding=ft.Padding.symmetric(horizontal=6, vertical=5),
                bgcolor="#1E2742" if is_main_active else ("#1A1E2E" if is_active_layer else "#141824"),
                border=ft.Border.all(
                    1.5 if is_main_active else 1,
                    ft.Colors.ORANGE_ACCENT_400 if is_main_active else ft.Colors.with_opacity(0.15, ft.Colors.WHITE),
                ),
                border_radius=ft.BorderRadius.all(10),
                width=80,
                on_click=lambda ev, l=li: switch_to(l, -1),
            )
            mask_list_col.controls.append(layer_card)

            # Sub-masks of this layer
            for si_idx, sm in enumerate(layer.mask.sub_masks):
                is_sm_sel = is_active_layer and state["sub_idx"] == si_idx
                sm_clr = ft.Colors.RED_300 if sm.mode == "erase" else ft.Colors.GREEN_ACCENT_400
                sm_ico = ft.Icons.REMOVE if sm.mode == "erase" else ft.Icons.ADD

                sm_card = ft.Container(
                    content=ft.Row([
                        ft.Container(width=6),  # indent
                        ft.Icon(sm_ico, size=12, color=sm_clr),
                        ft.Text(sm.name, size=10, color=ft.Colors.WHITE if is_sm_sel else ft.Colors.WHITE_60,
                                overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                    ], spacing=3),
                    padding=ft.Padding.symmetric(horizontal=4, vertical=5),
                    bgcolor="#1E2742" if is_sm_sel else "#0E121B",
                    border=ft.Border.all(1 if is_sm_sel else 0, sm_clr),
                    border_radius=ft.BorderRadius.all(7),
                    width=76,
                    margin=ft.Margin.only(left=4),
                    on_click=lambda ev, l=li, s=si_idx: switch_to(l, s),
                )
                mask_list_col.controls.append(sm_card)

        try:
            mask_list_col.update()
        except Exception:
            pass

    mask_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Container(height=4),
                mask_list_col,
            ],
            scroll=ft.ScrollMode.AUTO,
        ),
        right=0,
        top=0,
        bottom=0,
        width=88,
        bgcolor=ft.Colors.with_opacity(0.88, "#0D1120"),
        border_radius=ft.BorderRadius.only(top_left=12, bottom_left=12),
        padding=ft.Padding.symmetric(horizontal=4, vertical=4),
    )

    # ============================================================
    # Switching editing target
    # ============================================================
    def save_buf():
        """Write im_buf back to current editing target."""
        mi = state["main_idx"]
        si = state["sub_idx"]
        layer = project.layers[mi]
        if si == -1:
            layer.mask.data = im_buf.copy()
        else:
            if si < len(layer.mask.sub_masks):
                layer.mask.sub_masks[si].data = im_buf.copy()

    def load_buf(mi: int, si: int):
        """Load editing target's data into im_buf (at preview res)."""
        nonlocal im_buf
        im_buf = _load_target_buf(project, mi, si, prev_h, prev_w)

    def switch_to(mi: int, si: int):
        save_buf()
        state["main_idx"] = mi
        state["sub_idx"] = si
        load_buf(mi, si)
        project.selected_layer = project.layers[mi]
        rebuild_mask_list()
        rebuild_tool_options()
        refresh_canvas()

    # ============================================================
    # Add masks
    # ============================================================
    def on_add_main_mask():
        """Add a fresh brush layer and switch to editing it."""
        save_buf()
        new_layer = project.add_layer(mask_type="brush")
        mi = project.layers.index(new_layer)
        state["main_idx"] = mi
        state["sub_idx"] = -1
        state["tool"] = "brush"
        load_buf(mi, -1)
        rebuild_mask_list()
        rebuild_tool_options()
        refresh_canvas()

    def on_add_sub(li: int, mode: str):
        """Add a sub-mask to layer[li]."""
        save_buf()
        layer = project.layers[li]
        sm = layer.mask.add_sub_mask(mode=mode, mask_type="brush", size=(prev_h, prev_w))
        si_new = len(layer.mask.sub_masks) - 1
        state["main_idx"] = li
        state["sub_idx"] = si_new
        state["tool"] = "brush"
        load_buf(li, si_new)
        rebuild_mask_list()
        rebuild_tool_options()
        refresh_canvas()

    def toggle_vis(layer):
        layer.visible = not layer.visible
        rebuild_mask_list()

    # ============================================================
    # Mask operations (invert, clear, fill)
    # ============================================================
    def op_invert(e=None):
        np.copyto(im_buf, np.clip(1.0 - im_buf, 0.0, 1.0))
        refresh_canvas()

    def op_clear(e=None):
        im_buf.fill(0.0)
        refresh_canvas()

    def op_fill(e=None):
        im_buf.fill(1.0)
        refresh_canvas()

    # ============================================================
    # Tool Options (dynamic panel above tool bar)
    # ============================================================
    tool_options_container = ft.Container(
        bgcolor="#111521",
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        height=60,
    )

    def rebuild_tool_options():
        tool = state["tool"]
        if tool in ("brush", "eraser"):
            def on_sz(e): state["brush_sz"] = float(e.control.value)
            def on_fth(e): state["feather"] = float(e.control.value)
            tool_options_container.content = ft.Row([
                ft.Text("Size", size=11, color=ft.Colors.WHITE_70),
                ft.Slider(min=5, max=120, value=state["brush_sz"], expand=True,
                          active_color=ft.Colors.ORANGE_ACCENT_400, on_change=on_sz),
                ft.Text("Soft", size=11, color=ft.Colors.WHITE_70),
                ft.Slider(min=0, max=1, value=state["feather"], expand=True,
                          active_color=ft.Colors.ORANGE_ACCENT_400, on_change=on_fth),
            ], spacing=6)

        elif tool == "radial":
            def on_rx(e):
                state["rad_rx"] = prev_w * float(e.control.value)
                state["rad_ry"] = prev_h * float(e.control.value)
                apply_radial()
            def on_rf(e):
                state["rad_fth"] = float(e.control.value)
                apply_radial()
            tool_options_container.content = ft.Row([
                ft.Icon(ft.Icons.TOUCH_APP, size=14, color=ft.Colors.ORANGE_ACCENT_200),
                ft.Text("Tap to place center", size=11, color=ft.Colors.WHITE_60),
                ft.Text("R", size=11, color=ft.Colors.WHITE_70),
                ft.Slider(min=0.1, max=0.8, value=state["rad_rx"] / max(1, prev_w),
                          expand=True, active_color=ft.Colors.ORANGE_ACCENT_400, on_change=on_rx),
            ], spacing=6)

        elif tool == "linear":
            def mk_dir(d, label):
                return ft.Container(
                    content=ft.Text(label, size=11, color=ft.Colors.WHITE),
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    bgcolor=ft.Colors.ORANGE_ACCENT_700 if state["lin_dir"] == d else "#1E2536",
                    border_radius=ft.BorderRadius.all(8),
                    on_click=lambda ev, _d=d: set_linear_dir(_d),
                )
            tool_options_container.content = ft.Row(
                controls=[mk_dir("top", "Sky"), mk_dir("bottom", "Ground"),
                           mk_dir("left", "Left"), mk_dir("right", "Right")],
                spacing=6, alignment=ft.MainAxisAlignment.CENTER,
            )

        elif tool == "color":
            def on_tol(e):
                state["col_tol"] = float(e.control.value)
                if state["col_rgb"]:
                    apply_color_range()
            tool_options_container.content = ft.Row([
                ft.Icon(ft.Icons.COLORIZE, size=14, color=ft.Colors.ORANGE_ACCENT_200),
                ft.Text("Tap image to pick", size=11, color=ft.Colors.WHITE_60),
                ft.Text("Tol", size=11, color=ft.Colors.WHITE_70),
                ft.Slider(min=0.05, max=0.75, value=state["col_tol"], expand=True,
                          active_color=ft.Colors.ORANGE_ACCENT_400, on_change=on_tol),
            ], spacing=6)

        try:
            tool_options_container.update()
        except Exception:
            pass

    def set_linear_dir(d: str):
        state["lin_dir"] = d
        apply_linear()
        rebuild_tool_options()

    # ============================================================
    # Tool bar
    # ============================================================
    tool_btn_map: dict[str, ft.Container] = {}

    def set_tool(tool: str):
        state["tool"] = tool
        for t, btn in tool_btn_map.items():
            btn.bgcolor = (
                ft.Colors.ORANGE_ACCENT_700 if t == tool else ft.Colors.TRANSPARENT
            )
            try:
                btn.update()
            except Exception:
                pass
        # Auto-apply shape masks when selected
        if tool == "radial":
            apply_radial()
        elif tool == "linear":
            apply_linear()
        rebuild_tool_options()

    TOOLS = [
        ("brush",  ft.Icons.BRUSH,                "Brush"),
        ("eraser", ft.Icons.AUTO_FIX_NORMAL,       "Erase"),
        ("radial", ft.Icons.RADIO_BUTTON_CHECKED,  "Radial"),
        ("linear", ft.Icons.GRADIENT,              "Linear"),
        ("color",  ft.Icons.COLORIZE,              "Color"),
    ]

    for t_key, t_icon, t_tip in TOOLS:
        tool_btn_map[t_key] = ft.Container(
            content=ft.Column([
                ft.Icon(t_icon, size=20, color=ft.Colors.WHITE),
                ft.Text(t_tip, size=9, color=ft.Colors.WHITE_70),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            bgcolor=ft.Colors.ORANGE_ACCENT_700 if t_key == state["tool"] else ft.Colors.TRANSPARENT,
            border_radius=ft.BorderRadius.all(10),
            on_click=lambda ev, t=t_key: set_tool(t),
        )

    tool_bar = ft.Container(
        content=ft.Row(
            controls=list(tool_btn_map.values()),
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
        ),
        bgcolor="#161B26",
        padding=ft.Padding.symmetric(horizontal=8, vertical=6),
    )

    # ============================================================
    # Done → save & return
    # ============================================================
    async def save_and_done(e):
        save_buf()
        mi = state["main_idx"]
        layer = project.layers[mi]
        # Invalidate from this layer upward
        idx = project.layers.index(layer)
        project.invalidate_cache(idx)
        project.selected_layer = layer
        project.save()
        await page.push_route("/editor")

    # ============================================================
    # Compose stack + initialize
    # ============================================================
    rebuild_mask_list()
    rebuild_tool_options()

    canvas_stack = ft.Stack(
        controls=[gesture_canvas, mask_panel],
        expand=True,
    )

    return ft.View(
        route="/editor/selector",
        bgcolor="#0B0F17",
        appbar=ft.AppBar(
            bgcolor="#111521",
            title=ft.Text(
                f"Mask: {project.layers[state['main_idx']].name}",
                size=15, weight=ft.FontWeight.BOLD,
            ),
            actions=[
                ft.IconButton(ft.Icons.INVERT_COLORS, tooltip="Invert", on_click=op_invert),
                ft.IconButton(ft.Icons.CLEAR,         tooltip="Clear",  on_click=op_clear),
                ft.IconButton(ft.Icons.SELECT_ALL,    tooltip="Fill",   on_click=op_fill),
                ft.IconButton(
                    ft.Icons.CHECK,
                    icon_color=ft.Colors.GREEN_ACCENT_400,
                    tooltip="Done",
                    on_click=save_and_done,
                ),
            ],
        ),
        controls=[
            ft.SafeArea(
                content=ft.Column(
                    controls=[
                        canvas_stack,        # image + mask list overlay, expand
                        tool_options_container,
                        tool_bar,
                    ],
                    expand=True,
                    spacing=0,
                ),
                expand=True,
            )
        ],
    )


# ===========================================================================
# Helpers
# ===========================================================================

def _safe_at(obj, h: int, w: int) -> np.ndarray:
    """Safely resize a Mask or SubMask to (h, w) with fallback."""
    if obj is None:
        return np.ones((h, w), dtype=np.float32)
    data = obj.data if hasattr(obj, "data") else np.ones((h, w), dtype=np.float32)
    if data.shape[:2] == (h, w):
        return data
    return cv2.resize(data, (w, h), interpolation=cv2.INTER_LINEAR)


def _load_target_buf(project, mi: int, si: int, ph: int, pw: int) -> np.ndarray:
    """Load the mask data for target (mi, si) resized to (ph, pw)."""
    if mi >= len(project.layers):
        return np.zeros((ph, pw), dtype=np.float32)
    layer = project.layers[mi]
    if layer.mask is None:
        return np.ones((ph, pw), dtype=np.float32) if mi == 0 else np.zeros((ph, pw), dtype=np.float32)
    if si == -1:
        return _safe_at(layer.mask, ph, pw).copy()
    if 0 <= si < len(layer.mask.sub_masks):
        return _safe_at(layer.mask.sub_masks[si], ph, pw).copy()
    return np.zeros((ph, pw), dtype=np.float32)


def _apply_feather(buf: np.ndarray, brush_sz: float, feather: float):
    if feather > 0.05:
        sigma = max(0.5, (brush_sz / 2.0) * feather * 0.5)
        ksize = int(sigma * 4) | 1
        blurred = cv2.GaussianBlur(buf, (ksize, ksize), sigmaX=sigma)
        np.copyto(buf, np.clip(blurred, 0.0, 1.0))


def get_mask_icon(mask_type: str):
    return {
        "global": ft.Icons.PUBLIC,
        "brush": ft.Icons.BRUSH,
        "radial": ft.Icons.RADIO_BUTTON_CHECKED,
        "linear": ft.Icons.GRADIENT,
        "color": ft.Icons.COLORIZE,
        "luminance": ft.Icons.BRIGHTNESS_6,
    }.get(mask_type, ft.Icons.LAYERS)
