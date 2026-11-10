"""
Mask Studio — selector_view
Layout:
  AppBar (with title, show/hide panel toggle, done)
  Stack(expand) [
    GestureDetector(image, full area)
    MaskListPanel (right=0, overlay, semi-transparent, toggleable)
  ]
  ToolOptionsBar (dynamic per tool: Brush, Eraser, Radial, Linear, Color)
  ToolBar (bottom navigation)
"""

import flet as ft
from app import ReColor
from utils import arr_to_jpeg_bytes, create_mask_overlay, get_projects_dir
from backend.backend import Layer, Mask, SubMask
import numpy as np
import cv2
import time
import datetime
from pathlib import Path

# ---- Colour constants for sub-mask modes ----
ERASE_COLOR = (60, 100, 255)  # blue tint for erase sub-masks
PAINT_COLOR = (50, 200, 100)  # green tint for paint sub-masks
MAIN_COLOR = (255, 45, 45)  # red rubylith for main/effective


def selector_view(page: ft.Page, app: ReColor) -> ft.View:
    page.overlay.clear()
    pm = app.projects_manager

    if pm.project is None:
        pm.create_project("Default", r"D:\Projects\recolor\default.jpg")

    project = pm.project

    # Ensure file_picker is accessible
    if hasattr(app, "file_picker") and app.file_picker is not None:
        if hasattr(page, "services") and app.file_picker not in page.services:
            page.services.append(app.file_picker)

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

    # Fast low-res preview buffer (<= 360px max side) for silky smooth live interaction
    fast_scale = min(1.0, 360.0 / float(max(prev_h, prev_w)))
    fast_w = max(1, int(round(prev_w * fast_scale)))
    fast_h = max(1, int(round(prev_h * fast_scale)))
    fast_prev_arr = (
        cv2.resize(prev_arr, (fast_w, fast_h), interpolation=cv2.INTER_AREA)
        if fast_scale < 1.0
        else prev_arr
    )
    fast_y_grid, fast_x_grid = np.ogrid[:fast_h, :fast_w]
    fast_im_buf = np.zeros((fast_h, fast_w), dtype=np.float32)

    # Full preview coordinate grid
    y_grid, x_grid = np.ogrid[:prev_h, :prev_w]

    # ===========================================================
    # Mutable editing state
    # ===========================================================
    state = {
        "main_idx": project.layers.index(init_layer),
        "sub_idx": -1,  # -1 = editing main mask, >=0 = sub-mask
        "tool": "brush",  # brush | eraser | radial | linear | color
        "brush_sz": 28.0,
        "feather": 0.3,
        # Radial settings
        "rad_cx": prev_w / 2.0,
        "rad_cy": prev_h / 2.0,
        "rad_width": prev_w * 0.35,
        "rad_height": prev_h * 0.35,
        "rad_feather": 0.5,
        "rad_rot": 0.0,
        # Linear settings (Size removed; controlled by center, feather & rotation)
        "lin_cx": prev_w / 2.0,
        "lin_cy": prev_h / 2.0,
        "lin_feather": 0.5,
        "lin_deg": 270.0,  # 270 = Sky/Top, 90 = Ground, 180 = Left, 0 = Right
        # Color range
        "col_rgb": None,
        "col_tol": 0.35,
    }

    # Canvas viewport tracking (updated via on_size_change)
    viewport = [360.0, 420.0]

    # Working mask buffer at preview resolution
    im_buf: np.ndarray = _load_target_buf(
        project, state["main_idx"], state["sub_idx"], prev_h, prev_w
    )
    cv2.resize(
        im_buf, (fast_w, fast_h), dst=fast_im_buf, interpolation=cv2.INTER_LINEAR
    )

    stroke_pts: list[tuple[float, float]] = []
    last_refresh_time = [0.0]
    panel_visible = [True]

    # ============================================================
    # Coordinate mapping
    # ============================================================
    def to_img(x: float, y: float) -> tuple[float, float]:
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
    def render_canvas(fast: bool = False) -> bytes:
        """
        Compose rubylith overlay using either low-res fast buffer or full preview buffer.
        CRITICAL: The output JPEG is ALWAYS scaled back to (prev_w, prev_h) so that
        the canvas image and containers NEVER shrink or change size on screen.
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
            main_data = _safe_at(layer.mask, ch, cw)

        result = main_data.copy()
        for s_i, sm in enumerate(layer.mask.sub_masks):
            sm_data = target_buf if s_i == si else _safe_at(sm, ch, cw)
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

        # If fast preview was used, fast-upscale back to (prev_w, prev_h) via nearest neighbor (< 0.1ms)
        # This keeps the image widget's intrinsic size completely constant so canvas never shrinks!
        if fast and (cw != prev_w or ch != prev_h):
            overlay = cv2.resize(
                overlay, (prev_w, prev_h), interpolation=cv2.INTER_NEAREST
            )

        return arr_to_jpeg_bytes(overlay, quality=jpeg_q)

    # ============================================================
    # Canvas Image + GestureDetector
    # ============================================================
    img_disp = ft.Image(
        src=render_canvas(fast=False),
        fit=ft.BoxFit.CONTAIN,
        expand=True,
        gapless_playback=True,
    )

    def refresh_canvas(fast: bool = False):
        img_disp.src = render_canvas(fast=fast)
        try:
            img_disp.update()
        except Exception:
            pass

    def on_canvas_size(e):
        viewport[0] = float(e.width or 360)
        viewport[1] = float(e.height or 420)

    # ============================================================
    # Mask Generators (Radial, Linear, Color)
    # ============================================================
    def apply_radial(fast: bool = False):
        fth = float(np.clip(state["rad_feather"], 0.01, 0.99))
        deg = float(state["rad_rot"])

        if fast:
            cx = state["rad_cx"] * fast_scale
            cy = state["rad_cy"] * fast_scale
            rx = max(1.0, float(state["rad_width"]) * fast_scale)
            ry = max(1.0, float(state["rad_height"]) * fast_scale)

            dx = fast_x_grid - cx
            dy = fast_y_grid - cy
            if deg != 0.0:
                rad = np.radians(deg)
                cos_a, sin_a = np.cos(rad), np.sin(rad)
                xr = dx * cos_a + dy * sin_a
                yr = -dx * sin_a + dy * cos_a
            else:
                xr, yr = dx, dy

            dist = np.sqrt((xr / rx) ** 2 + (yr / ry) ** 2)
            inner = 1.0 - fth
            grad = np.clip(1.0 - (dist - inner) / fth, 0.0, 1.0).astype(np.float32)
            np.copyto(fast_im_buf, grad)
            refresh_canvas(fast=True)
        else:
            cx = state["rad_cx"]
            cy = state["rad_cy"]
            rx = max(1.0, float(state["rad_width"]))
            ry = max(1.0, float(state["rad_height"]))

            dx = x_grid - cx
            dy = y_grid - cy
            if deg != 0.0:
                rad = np.radians(deg)
                cos_a, sin_a = np.cos(rad), np.sin(rad)
                xr = dx * cos_a + dy * sin_a
                yr = -dx * sin_a + dy * cos_a
            else:
                xr, yr = dx, dy

            dist = np.sqrt((xr / rx) ** 2 + (yr / ry) ** 2)
            inner = 1.0 - fth
            grad = np.clip(1.0 - (dist - inner) / fth, 0.0, 1.0).astype(np.float32)
            np.copyto(im_buf, grad)
            cv2.resize(
                im_buf,
                (fast_w, fast_h),
                dst=fast_im_buf,
                interpolation=cv2.INTER_LINEAR,
            )
            refresh_canvas(fast=False)

    def apply_linear(fast: bool = False):
        deg = float(state["lin_deg"])
        rad = np.radians(deg)
        ux, uy = np.cos(rad), np.sin(rad)
        fth = float(np.clip(state["lin_feather"], 0.05, 0.95))

        if fast:
            cx = state["lin_cx"] * fast_scale
            cy = state["lin_cy"] * fast_scale
            span = max(3.0, (min(fast_w, fast_h) * 0.7) * fth)

            p = (fast_x_grid - cx) * ux + (fast_y_grid - cy) * uy
            t = np.clip(0.5 - p / span, 0.0, 1.0)
            t = (t * t * (3.0 - 2.0 * t)).astype(np.float32)
            np.copyto(fast_im_buf, t)
            refresh_canvas(fast=True)
        else:
            cx = state["lin_cx"]
            cy = state["lin_cy"]
            span = max(5.0, (min(prev_w, prev_h) * 0.7) * fth)

            p = (x_grid - cx) * ux + (y_grid - cy) * uy
            t = np.clip(0.5 - p / span, 0.0, 1.0)
            t = (t * t * (3.0 - 2.0 * t)).astype(np.float32)
            np.copyto(im_buf, t)
            cv2.resize(
                im_buf,
                (fast_w, fast_h),
                dst=fast_im_buf,
                interpolation=cv2.INTER_LINEAR,
            )
            refresh_canvas(fast=False)

    def apply_color_range():
        if state["col_rgb"] is None:
            return
        rgb = prev_arr[..., :3].astype(np.float32)
        target = np.array(state["col_rgb"], dtype=np.float32)
        dist = np.linalg.norm(rgb - target, axis=2) / 441.67
        tol = max(0.01, state["col_tol"])
        f = 0.2
        new = np.clip(1.0 - (dist - tol * (1.0 - f)) / (tol * f), 0.0, 1.0).astype(
            np.float32
        )
        np.copyto(im_buf, new)
        cv2.resize(
            im_buf, (fast_w, fast_h), dst=fast_im_buf, interpolation=cv2.INTER_LINEAR
        )
        refresh_canvas(fast=False)

    # --- Touch / Drag handlers ---
    def on_pan_start(e: ft.DragStartEvent):
        tool = state["tool"]
        ix, iy = to_img(e.local_position.x, e.local_position.y)

        if tool in ("brush", "eraser"):
            stroke_pts.clear()
            stroke_pts.append((ix, iy))
            color = 0.0 if tool == "eraser" else 1.0
            r = max(1, int(round(state["brush_sz"] / 2.0)))
            cv2.circle(
                im_buf, (int(round(ix)), int(round(iy))), r, color, -1, cv2.LINE_AA
            )
            fr = max(1, int(round(r * fast_scale)))
            cv2.circle(
                fast_im_buf,
                (int(round(ix * fast_scale)), int(round(iy * fast_scale))),
                fr,
                color,
                -1,
                cv2.LINE_AA,
            )
            last_refresh_time[0] = time.perf_counter()
            refresh_canvas(fast=True)

        elif tool == "radial":
            state["rad_cx"] = ix
            state["rad_cy"] = iy
            apply_radial(fast=True)

        elif tool == "linear":
            state["lin_cx"] = ix
            state["lin_cy"] = iy
            apply_linear(fast=True)

    def on_pan_update(e: ft.DragUpdateEvent):
        tool = state["tool"]
        ix, iy = to_img(e.local_position.x, e.local_position.y)

        if tool in ("brush", "eraser"):
            color = 0.0 if tool == "eraser" else 1.0
            r = max(1, int(round(state["brush_sz"] / 2.0)))
            thick = max(1, int(round(state["brush_sz"])))

            if stroke_pts:
                px, py = stroke_pts[-1]
                cv2.line(
                    im_buf,
                    (int(round(px)), int(round(py))),
                    (int(round(ix)), int(round(iy))),
                    color,
                    thick,
                    cv2.LINE_AA,
                )
                cv2.line(
                    fast_im_buf,
                    (int(round(px * fast_scale)), int(round(py * fast_scale))),
                    (int(round(ix * fast_scale)), int(round(iy * fast_scale))),
                    color,
                    max(1, int(round(thick * fast_scale))),
                    cv2.LINE_AA,
                )
            cv2.circle(
                im_buf, (int(round(ix)), int(round(iy))), r, color, -1, cv2.LINE_AA
            )
            cv2.circle(
                fast_im_buf,
                (int(round(ix * fast_scale)), int(round(iy * fast_scale))),
                max(1, int(round(r * fast_scale))),
                color,
                -1,
                cv2.LINE_AA,
            )
            stroke_pts.append((ix, iy))

            now = time.perf_counter()
            if now - last_refresh_time[0] >= 0.033:  # 30 FPS limit during active drag
                last_refresh_time[0] = now
                refresh_canvas(fast=True)

        elif tool == "radial":
            state["rad_cx"] = ix
            state["rad_cy"] = iy
            now = time.perf_counter()
            if now - last_refresh_time[0] >= 0.033:
                last_refresh_time[0] = now
                apply_radial(fast=True)

        elif tool == "linear":
            state["lin_cx"] = ix
            state["lin_cy"] = iy
            now = time.perf_counter()
            if now - last_refresh_time[0] >= 0.033:
                last_refresh_time[0] = now
                apply_linear(fast=True)

    def on_pan_end(e: ft.DragEndEvent):
        tool = state["tool"]
        if tool in ("brush", "eraser"):
            if state["feather"] > 0.05 and stroke_pts:
                _apply_stroke_feather(
                    im_buf,
                    stroke_pts,
                    state["brush_sz"],
                    state["feather"],
                    prev_h,
                    prev_w,
                )
            stroke_pts.clear()
            cv2.resize(
                im_buf,
                (fast_w, fast_h),
                dst=fast_im_buf,
                interpolation=cv2.INTER_LINEAR,
            )
            refresh_canvas(fast=False)
        elif tool == "radial":
            apply_radial(fast=False)
        elif tool == "linear":
            apply_linear(fast=False)

    def on_tap_up(e: ft.TapEvent):
        ix, iy = to_img(e.local_position.x, e.local_position.y)
        px, py = int(round(ix)), int(round(iy))
        tool = state["tool"]

        if tool == "color":
            rgb = tuple(int(c) for c in prev_arr[py, px][:3])
            state["col_rgb"] = rgb
            apply_color_range()
            rebuild_tool_options()

        elif tool == "radial":
            # Tap to add/position radial mask
            state["rad_cx"] = ix
            state["rad_cy"] = iy
            apply_radial(fast=False)

        elif tool == "linear":
            # Tap to add/position linear mask
            state["lin_cx"] = ix
            state["lin_cy"] = iy
            apply_linear(fast=False)

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
    # Switching editing target & persistence
    # ============================================================
    def save_buf():
        """Write im_buf back to current editing target."""
        mi = state["main_idx"]
        si = state["sub_idx"]
        if mi >= len(project.layers):
            return
        layer = project.layers[mi]
        if si == -1:
            layer.mask.data = im_buf.copy()
        else:
            if 0 <= si < len(layer.mask.sub_masks):
                layer.mask.sub_masks[si].data = im_buf.copy()

    def load_buf(mi: int, si: int):
        """Load editing target's data into im_buf (at preview res)."""
        nonlocal im_buf, fast_im_buf
        im_buf = _load_target_buf(project, mi, si, prev_h, prev_w)
        cv2.resize(
            im_buf, (fast_w, fast_h), dst=fast_im_buf, interpolation=cv2.INTER_LINEAR
        )

    def switch_to(mi: int, si: int):
        save_buf()
        state["main_idx"] = mi
        state["sub_idx"] = si
        load_buf(mi, si)
        project.selected_layer = project.layers[mi]
        appbar_title.value = f"Mask: {project.layers[mi].name}"
        try:
            appbar_title.update()
        except Exception:
            pass
        rebuild_mask_list()
        rebuild_tool_options()
        refresh_canvas(fast=False)

    def on_add_main_mask():
        """Add a fresh brush layer (M1, M2, etc.) and switch to editing it."""
        save_buf()
        new_layer = project.add_layer(mask_type="brush")
        mi = project.layers.index(new_layer)
        switch_to(mi, -1)

    def on_add_sub(li: int, mode: str):
        """Add a sub-mask (child mask) to layer[li]."""
        save_buf()
        layer = project.layers[li]
        layer.mask.add_sub_mask(mode=mode, mask_type="brush", size=(prev_h, prev_w))
        si_new = len(layer.mask.sub_masks) - 1
        state["tool"] = "brush"
        switch_to(li, si_new)

    def toggle_vis(layer: Layer):
        layer.visible = not layer.visible
        rebuild_mask_list()

    # ============================================================
    # Mask card context options (Parent & Child)
    # ============================================================
    def show_alert(title: str, msg: str):
        dlg = ft.AlertDialog(
            title=ft.Text(
                title, size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
            ),
            content=ft.Text(msg, size=12, color=ft.Colors.WHITE_70),
            actions=[
                ft.Button(content="OK", on_click=lambda ev: page.pop_dialog()),
            ],
            bgcolor="#151A27",
        )
        page.show_dialog(dlg)

    def on_export_mask_image(li: int):
        page.pop_dialog()
        layer = project.layers[li]
        eff_mask = layer.mask.compute_effective(project.image_array.shape[:2])
        bw = (np.clip(eff_mask, 0.0, 1.0) * 255.0).astype(np.uint8)

        export_dir = get_projects_dir(page).parent / "exports" / "masks"
        export_dir.mkdir(parents=True, exist_ok=True)
        safe_name = (
            "".join(
                c for c in layer.name if c.isalnum() or c in (" ", "_", "-")
            ).strip()
            or "mask"
        )
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = export_dir / f"{safe_name}_{ts}.png"

        try:
            cv2.imwrite(str(export_path), bw)
            show_alert(
                "Mask Exported",
                f"Successfully exported black & white mask image to:\n{export_path}",
            )
        except Exception as ex:
            show_alert("Export Failed", f"Could not save mask: {ex}")

    async def on_import_mask_image(li: int):
        page.pop_dialog()
        layer = project.layers[li]
        try:
            files = await app.file_picker.pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE,
            )
            if not files or len(files) == 0:
                return

            import_path = files[0].path
            imp_img = cv2.imread(str(import_path), cv2.IMREAD_UNCHANGED)
            if imp_img is None:
                show_alert(
                    "Import Failed", f"Could not load image file:\n{import_path}"
                )
                return

            ih, iw = imp_img.shape[:2]
            oh, ow = project.image_array.shape[:2]

            imp_ratio = iw / float(ih)
            our_ratio = ow / float(oh)

            # Check aspect ratio tolerance (5%)
            if abs(imp_ratio - our_ratio) / our_ratio > 0.05:
                show_alert(
                    "Aspect Ratio Mismatch",
                    f"Selected image ratio is {iw}x{ih} ({imp_ratio:.2f}:1), "
                    f"but project image ratio is {ow}x{oh} ({our_ratio:.2f}:1).\n"
                    "Aspect ratio must match the project image.",
                )
                return

            # Convert to grayscale float32 [0.0, 1.0]
            if imp_img.ndim == 3:
                if imp_img.shape[2] == 4:
                    gray = cv2.cvtColor(imp_img, cv2.COLOR_BGRA2GRAY)
                else:
                    gray = cv2.cvtColor(imp_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = imp_img

            mask_data = gray.astype(np.float32) / 255.0
            full_mask = cv2.resize(mask_data, (ow, oh), interpolation=cv2.INTER_LINEAR)

            layer.mask.data = full_mask

            # Update live buffer if this layer is active
            if state["main_idx"] == li and state["sub_idx"] == -1:
                np.copyto(
                    im_buf,
                    cv2.resize(
                        full_mask, (prev_w, prev_h), interpolation=cv2.INTER_LINEAR
                    ),
                )
                cv2.resize(
                    im_buf,
                    (fast_w, fast_h),
                    dst=fast_im_buf,
                    interpolation=cv2.INTER_LINEAR,
                )

            refresh_canvas(fast=False)
            rebuild_mask_list()
            show_alert(
                "Import Succeeded", f"Replaced mask with '{Path(import_path).name}'."
            )
        except Exception as ex:
            show_alert("Import Error", f"An error occurred: {ex}")

    def on_rename_layer(li: int):
        page.pop_dialog()
        layer = project.layers[li]
        tf = ft.TextField(value=layer.name, label="Layer Name", autofocus=True)

        def do_rename(ev):
            new_name = tf.value.strip()
            if new_name:
                layer.name = new_name
                rebuild_mask_list()
                appbar_title.value = f"Mask: {new_name}"
                try:
                    appbar_title.update()
                except Exception:
                    pass
            page.pop_dialog()

        dlg = ft.AlertDialog(
            title=ft.Text(
                "Rename Mask Layer",
                size=15,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.WHITE,
            ),
            content=tf,
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: page.pop_dialog()),
                ft.Button(content="Save", on_click=do_rename),
            ],
            bgcolor="#151A27",
        )
        page.show_dialog(dlg)

    def on_delete_layer(li: int):
        page.pop_dialog()
        layer = project.layers[li]
        if len(project.layers) <= 1:
            layer.mask.clear()
            if state["main_idx"] == 0:
                im_buf.fill(0.0)
                fast_im_buf.fill(0.0)
            refresh_canvas(fast=False)
            return
        project.remove_layer(layer)
        new_mi = min(li, len(project.layers) - 1)
        switch_to(new_mi, -1)

    def op_invert():
        np.copyto(im_buf, np.clip(1.0 - im_buf, 0.0, 1.0))
        cv2.resize(
            im_buf, (fast_w, fast_h), dst=fast_im_buf, interpolation=cv2.INTER_LINEAR
        )
        refresh_canvas(fast=False)

    def op_fill():
        im_buf.fill(1.0)
        fast_im_buf.fill(1.0)
        refresh_canvas(fast=False)

    def show_parent_options(li: int):
        layer = project.layers[li]

        def mk_opt(icon, title, on_click, color=ft.Colors.WHITE):
            return ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(icon, size=17, color=color),
                        ft.Text(
                            title, size=13, color=color, weight=ft.FontWeight.W_500
                        ),
                    ],
                    spacing=12,
                ),
                padding=ft.Padding.symmetric(horizontal=16, vertical=11),
                border_radius=ft.BorderRadius.all(8),
                on_click=on_click,
            )

        content_col = ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(
                            get_mask_icon(layer.mask_type),
                            size=16,
                            color=ft.Colors.ORANGE_ACCENT_400,
                        ),
                        ft.Text(
                            f"{layer.name} Options",
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                            expand=True,
                        ),
                        ft.IconButton(
                            ft.Icons.CLOSE,
                            icon_size=16,
                            on_click=lambda ev: page.pop_dialog(),
                        ),
                    ],
                    spacing=6,
                ),
                ft.Divider(color=ft.Colors.WHITE_12, height=1),
                mk_opt(
                    ft.Icons.FILE_UPLOAD,
                    "Import & Replace",
                    lambda ev: page.run_task(on_import_mask_image, li),
                ),
                mk_opt(
                    ft.Icons.FILE_DOWNLOAD,
                    "Export as Image",
                    lambda ev: on_export_mask_image(li),
                ),
                ft.Divider(color=ft.Colors.WHITE_12, height=1),
                mk_opt(
                    ft.Icons.REMOVE_CIRCLE_OUTLINE,
                    "Erase Child",
                    lambda ev: (page.pop_dialog(), on_add_sub(li, "erase")),
                    ft.Colors.RED_300,
                ),
                mk_opt(
                    ft.Icons.ADD_CIRCLE_OUTLINE,
                    "Paint Child",
                    lambda ev: (page.pop_dialog(), on_add_sub(li, "paint")),
                    ft.Colors.GREEN_ACCENT_400,
                ),
                ft.Divider(color=ft.Colors.WHITE_12, height=1),
                mk_opt(
                    ft.Icons.INVERT_COLORS,
                    "Invert",
                    lambda ev: (page.pop_dialog(), op_invert()),
                ),
                mk_opt(
                    ft.Icons.CONTENT_COPY,
                    "Duplicate",
                    lambda ev: (page.pop_dialog(), on_dup_layer(li)),
                ),
                mk_opt(
                    ft.Icons.FORMAT_COLOR_FILL,
                    "Fill",
                    lambda ev: (page.pop_dialog(), op_fill()),
                ),
                ft.Divider(color=ft.Colors.WHITE_12, height=1),
                mk_opt(ft.Icons.EDIT, "Rename", lambda ev: on_rename_layer(li)),
                mk_opt(
                    ft.Icons.VISIBILITY if layer.visible else ft.Icons.VISIBILITY_OFF,
                    "Hide Layer" if layer.visible else "Show Layer",
                    lambda ev: (page.pop_dialog(), toggle_vis(layer)),
                ),
                mk_opt(
                    ft.Icons.DELETE_OUTLINE,
                    "Delete",
                    lambda ev: on_delete_layer(li),
                    ft.Colors.RED_ACCENT_400,
                ),
            ],
            spacing=2,
            scroll=ft.ScrollMode.AUTO,
        )

        sheet = ft.BottomSheet(
            content=ft.Container(
                content=content_col,
                bgcolor="#121624",
                padding=ft.Padding.all(12),
                border_radius=ft.BorderRadius.only(top_left=16, top_right=16),
            ),
        )
        page.show_dialog(sheet)

    def on_dup_layer(li: int):
        save_buf()
        dup = project.duplicate_layer(project.layers[li])
        mi = project.layers.index(dup)
        switch_to(mi, -1)

    def show_child_options(li: int, si: int):
        layer = project.layers[li]
        if si >= len(layer.mask.sub_masks):
            return
        sm = layer.mask.sub_masks[si]

        def move_child(delta: int):
            page.pop_dialog()
            save_buf()
            n_idx = si + delta
            if 0 <= n_idx < len(layer.mask.sub_masks):
                layer.mask.sub_masks[si], layer.mask.sub_masks[n_idx] = (
                    layer.mask.sub_masks[n_idx],
                    layer.mask.sub_masks[si],
                )
                switch_to(li, n_idx)

        def delete_child():
            page.pop_dialog()
            save_buf()
            if 0 <= si < len(layer.mask.sub_masks):
                del layer.mask.sub_masks[si]
            switch_to(li, -1)

        sheet = ft.BottomSheet(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(
                                    (
                                        ft.Icons.REMOVE
                                        if sm.mode == "erase"
                                        else ft.Icons.ADD
                                    ),
                                    size=16,
                                    color=(
                                        ft.Colors.RED_300
                                        if sm.mode == "erase"
                                        else ft.Colors.GREEN_ACCENT_400
                                    ),
                                ),
                                ft.Text(
                                    f"{sm.name} ({sm.mode.title()})",
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE,
                                    expand=True,
                                ),
                                ft.IconButton(
                                    ft.Icons.CLOSE,
                                    icon_size=16,
                                    on_click=lambda ev: page.pop_dialog(),
                                ),
                            ]
                        ),
                        ft.Divider(color=ft.Colors.WHITE_12, height=1),
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.ARROW_UPWARD,
                                        size=17,
                                        color=(
                                            ft.Colors.WHITE
                                            if si > 0
                                            else ft.Colors.WHITE_24
                                        ),
                                    ),
                                    ft.Text(
                                        "Move Up",
                                        size=13,
                                        color=(
                                            ft.Colors.WHITE
                                            if si > 0
                                            else ft.Colors.WHITE_24
                                        ),
                                    ),
                                ],
                                spacing=12,
                            ),
                            padding=ft.Padding.symmetric(horizontal=16, vertical=11),
                            border_radius=ft.BorderRadius.all(8),
                            on_click=lambda ev: move_child(-1) if si > 0 else None,
                        ),
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.ARROW_DOWNWARD,
                                        size=17,
                                        color=(
                                            ft.Colors.WHITE
                                            if si < len(layer.mask.sub_masks) - 1
                                            else ft.Colors.WHITE_24
                                        ),
                                    ),
                                    ft.Text(
                                        "Move Down",
                                        size=13,
                                        color=(
                                            ft.Colors.WHITE
                                            if si < len(layer.mask.sub_masks) - 1
                                            else ft.Colors.WHITE_24
                                        ),
                                    ),
                                ],
                                spacing=12,
                            ),
                            padding=ft.Padding.symmetric(horizontal=16, vertical=11),
                            border_radius=ft.BorderRadius.all(8),
                            on_click=lambda ev: (
                                move_child(1)
                                if si < len(layer.mask.sub_masks) - 1
                                else None
                            ),
                        ),
                        ft.Divider(color=ft.Colors.WHITE_12, height=1),
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.DELETE_OUTLINE,
                                        size=17,
                                        color=ft.Colors.RED_ACCENT_400,
                                    ),
                                    ft.Text(
                                        "Delete",
                                        size=13,
                                        color=ft.Colors.RED_ACCENT_400,
                                        weight=ft.FontWeight.W_500,
                                    ),
                                ],
                                spacing=12,
                            ),
                            padding=ft.Padding.symmetric(horizontal=16, vertical=11),
                            border_radius=ft.BorderRadius.all(8),
                            on_click=lambda ev: delete_child(),
                        ),
                    ],
                    spacing=2,
                ),
                bgcolor="#121624",
                padding=ft.Padding.all(12),
                border_radius=ft.BorderRadius.only(top_left=16, top_right=16),
            ),
        )
        page.show_dialog(sheet)

    # ============================================================
    # Mask-list panel (overlaid right side)
    # ============================================================
    mask_list_col = ft.Column(spacing=5, scroll=ft.ScrollMode.AUTO)

    def rebuild_mask_list():
        mask_list_col.controls.clear()

        # [+] Add new main mask layer button (creates M1, M2, M3...)
        mask_list_col.controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.ADD, size=16, color=ft.Colors.ORANGE_ACCENT_400
                        ),
                        ft.Text(
                            "New",
                            size=10,
                            color=ft.Colors.ORANGE_ACCENT_400,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=2,
                ),
                width=80,
                height=32,
                bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.ORANGE_ACCENT_400),
                border=ft.Border.all(1, ft.Colors.ORANGE_ACCENT_400),
                border_radius=ft.BorderRadius.all(8),
                alignment=ft.Alignment.CENTER,
                tooltip="New Mask Layer",
                on_click=lambda ev: on_add_main_mask(),
            )
        )

        for li, layer in enumerate(project.layers):
            is_active_layer = li == state["main_idx"]
            is_main_active = is_active_layer and state["sub_idx"] == -1
            mi_icon = get_mask_icon(layer.mask_type)

            # Parent Mask card
            card_content = ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(
                                    mi_icon,
                                    size=13,
                                    color=(
                                        ft.Colors.ORANGE_ACCENT_400
                                        if is_active_layer
                                        else ft.Colors.WHITE_38
                                    ),
                                ),
                                ft.Text(
                                    layer.name,
                                    size=10,
                                    color=(
                                        ft.Colors.WHITE
                                        if is_active_layer
                                        else ft.Colors.WHITE_70
                                    ),
                                    weight=(
                                        ft.FontWeight.BOLD
                                        if is_main_active
                                        else ft.FontWeight.NORMAL
                                    ),
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True,
                                ),
                                ft.Container(
                                    content=ft.Icon(
                                        ft.Icons.MORE_VERT,
                                        size=13,
                                        color=ft.Colors.WHITE_54,
                                    ),
                                    on_click=lambda ev, l=li: show_parent_options(l),
                                    width=16,
                                    height=16,
                                    alignment=ft.Alignment.CENTER,
                                ),
                            ],
                            spacing=2,
                        ),
                        ft.Row(
                            [
                                ft.Text(
                                    (
                                        f"{len(layer.mask.sub_masks)} sub"
                                        if layer.mask.sub_masks
                                        else "main"
                                    ),
                                    size=9,
                                    color=ft.Colors.WHITE_38,
                                ),
                                ft.Container(expand=True),
                                ft.Container(
                                    content=ft.Icon(
                                        (
                                            ft.Icons.VISIBILITY
                                            if layer.visible
                                            else ft.Icons.VISIBILITY_OFF
                                        ),
                                        size=11,
                                        color=(
                                            ft.Colors.WHITE_60
                                            if layer.visible
                                            else ft.Colors.WHITE_24
                                        ),
                                    ),
                                    width=18,
                                    height=18,
                                    alignment=ft.Alignment.CENTER,
                                    on_click=lambda ev, l=layer: toggle_vis(l),
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=2,
                ),
                padding=ft.Padding.symmetric(horizontal=6, vertical=5),
                bgcolor=(
                    "#1E2742"
                    if is_main_active
                    else ("#1A1E2E" if is_active_layer else "#141824")
                ),
                border=ft.Border.all(
                    1.5 if is_main_active else 1,
                    (
                        ft.Colors.ORANGE_ACCENT_400
                        if is_main_active
                        else ft.Colors.with_opacity(0.15, ft.Colors.WHITE)
                    ),
                ),
                border_radius=ft.BorderRadius.all(9),
                width=80,
            )

            parent_gesture = ft.GestureDetector(
                content=card_content,
                on_tap=lambda ev, l=li: switch_to(l, -1),
                on_long_press_start=lambda ev, l=li: show_parent_options(l),
                on_secondary_tap=lambda ev, l=li: show_parent_options(l),
            )
            mask_list_col.controls.append(parent_gesture)

            # Child Sub-masks: can be moved up and down
            for si_idx, sm in enumerate(layer.mask.sub_masks):
                is_sm_sel = is_active_layer and state["sub_idx"] == si_idx
                sm_clr = (
                    ft.Colors.RED_300
                    if sm.mode == "erase"
                    else ft.Colors.GREEN_ACCENT_400
                )
                sm_ico = ft.Icons.REMOVE if sm.mode == "erase" else ft.Icons.ADD

                def make_move_cb(l, s, delta):
                    def cb(ev):
                        save_buf()
                        target = s + delta
                        if 0 <= target < len(project.layers[l].mask.sub_masks):
                            subs = project.layers[l].mask.sub_masks
                            subs[s], subs[target] = subs[target], subs[s]
                            switch_to(l, target)

                    return cb

                sm_card = ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(sm_ico, size=11, color=sm_clr),
                            ft.Text(
                                sm.name,
                                size=9,
                                color=(
                                    ft.Colors.WHITE if is_sm_sel else ft.Colors.WHITE_60
                                ),
                                overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True,
                            ),
                            # Up / Down quick reorder buttons
                            ft.Column(
                                [
                                    ft.Container(
                                        content=ft.Icon(
                                            ft.Icons.ARROW_DROP_UP,
                                            size=11,
                                            color=ft.Colors.WHITE_54,
                                        ),
                                        width=12,
                                        height=10,
                                        alignment=ft.Alignment.CENTER,
                                        on_click=make_move_cb(li, si_idx, -1),
                                    ),
                                    ft.Container(
                                        content=ft.Icon(
                                            ft.Icons.ARROW_DROP_DOWN,
                                            size=11,
                                            color=ft.Colors.WHITE_54,
                                        ),
                                        width=12,
                                        height=10,
                                        alignment=ft.Alignment.CENTER,
                                        on_click=make_move_cb(li, si_idx, 1),
                                    ),
                                ],
                                spacing=0,
                            ),
                        ],
                        spacing=2,
                    ),
                    padding=ft.Padding.symmetric(horizontal=4, vertical=4),
                    bgcolor="#1E2742" if is_sm_sel else "#0E121B",
                    border=ft.Border.all(
                        1 if is_sm_sel else 0.5,
                        sm_clr if is_sm_sel else ft.Colors.with_opacity(0.3, sm_clr),
                    ),
                    border_radius=ft.BorderRadius.all(7),
                    width=76,
                    margin=ft.Margin.only(left=4),
                )

                child_gesture = ft.GestureDetector(
                    content=sm_card,
                    on_tap=lambda ev, l=li, s=si_idx: switch_to(l, s),
                    on_long_press_start=lambda ev, l=li, s=si_idx: show_child_options(
                        l, s
                    ),
                    on_secondary_tap=lambda ev, l=li, s=si_idx: show_child_options(
                        l, s
                    ),
                )
                mask_list_col.controls.append(child_gesture)

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
        visible=panel_visible[0],
    )

    def toggle_panel():
        panel_visible[0] = not panel_visible[0]
        mask_panel.visible = panel_visible[0]
        panel_toggle_btn.icon_color = (
            ft.Colors.ORANGE_ACCENT_400 if panel_visible[0] else ft.Colors.WHITE_54
        )
        try:
            mask_panel.update()
            panel_toggle_btn.update()
        except Exception:
            pass

    panel_toggle_btn = ft.IconButton(
        ft.Icons.VIEW_SIDEBAR_ROUNDED,
        tooltip="Toggle Mask Panel",
        icon_color=ft.Colors.ORANGE_ACCENT_400,
        on_click=lambda ev: toggle_panel(),
    )

    # ============================================================
    # Tool Options Container (Height adjusted to 144px for full visibility)
    # ============================================================
    tool_options_container = ft.Container(
        bgcolor="#111521",
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        height=144,
    )

    def rebuild_tool_options():
        tool = state["tool"]

        if tool in ("brush", "eraser"):

            def on_sz(e):
                state["brush_sz"] = float(e.control.value)

            def on_fth(e):
                state["feather"] = float(e.control.value)

            tool_options_container.content = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                (
                                    ft.Icons.BRUSH
                                    if tool == "brush"
                                    else ft.Icons.AUTO_FIX_NORMAL
                                ),
                                size=14,
                                color=ft.Colors.ORANGE_ACCENT_400,
                            ),
                            ft.Text(
                                f"{tool.title()} Settings",
                                size=11,
                                color=ft.Colors.WHITE,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        spacing=6,
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                "Size", size=10, color=ft.Colors.WHITE_70, width=32
                            ),
                            ft.Slider(
                                min=5,
                                max=150,
                                value=state["brush_sz"],
                                expand=True,
                                active_color=ft.Colors.ORANGE_ACCENT_400,
                                on_change=on_sz,
                            ),
                        ],
                        spacing=4,
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                "Soft", size=10, color=ft.Colors.WHITE_70, width=32
                            ),
                            ft.Slider(
                                min=0,
                                max=1,
                                value=state["feather"],
                                expand=True,
                                active_color=ft.Colors.ORANGE_ACCENT_400,
                                on_change=on_fth,
                            ),
                        ],
                        spacing=4,
                    ),
                ],
                spacing=2,
            )

        elif tool == "radial":
            # Radial: Width, Height, Feather, Rotation
            rot_val_text = ft.Text(
                f"{int(round(state['rad_rot']))}°",
                size=10,
                color=ft.Colors.ORANGE_ACCENT_200,
            )

            def throttle_radial_fast():
                now = time.perf_counter()
                if now - last_refresh_time[0] >= 0.033:
                    last_refresh_time[0] = now
                    apply_radial(fast=True)

            def on_rx(e):
                state["rad_width"] = float(e.control.value)
                throttle_radial_fast()

            def on_rx_end(e):
                state["rad_width"] = float(e.control.value)
                apply_radial(fast=False)

            def on_ry(e):
                state["rad_height"] = float(e.control.value)
                throttle_radial_fast()

            def on_ry_end(e):
                state["rad_height"] = float(e.control.value)
                apply_radial(fast=False)

            def on_rf(e):
                state["rad_feather"] = float(e.control.value)
                throttle_radial_fast()

            def on_rf_end(e):
                state["rad_feather"] = float(e.control.value)
                apply_radial(fast=False)

            def on_rot(e):
                state["rad_rot"] = float(e.control.value)
                rot_val_text.value = f"{int(round(state['rad_rot']))}°"
                try:
                    rot_val_text.update()
                except Exception:
                    pass
                throttle_radial_fast()

            def on_rot_end(e):
                state["rad_rot"] = float(e.control.value)
                rot_val_text.value = f"{int(round(state['rad_rot']))}°"
                try:
                    rot_val_text.update()
                except Exception:
                    pass
                apply_radial(fast=False)

            tool_options_container.content = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.RADIO_BUTTON_CHECKED,
                                size=13,
                                color=ft.Colors.ORANGE_ACCENT_400,
                            ),
                            ft.Text(
                                "Radial Mask",
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Text(
                                "• Tap/drag canvas to place mask",
                                size=9,
                                color=ft.Colors.WHITE_54,
                                expand=True,
                            ),
                            ft.Text("Rot:", size=10, color=ft.Colors.WHITE_70),
                            rot_val_text,
                        ],
                        spacing=4,
                    ),
                    ft.Row(
                        [
                            ft.Text("W", size=10, color=ft.Colors.WHITE_70, width=16),
                            ft.Slider(
                                min=10,
                                max=prev_w * 1.5,
                                value=state["rad_width"],
                                expand=True,
                                active_color=ft.Colors.ORANGE_ACCENT_400,
                                on_change=on_rx,
                                on_change_end=on_rx_end,
                            ),
                            ft.Text("H", size=10, color=ft.Colors.WHITE_70, width=16),
                            ft.Slider(
                                min=10,
                                max=prev_h * 1.5,
                                value=state["rad_height"],
                                expand=True,
                                active_color=ft.Colors.ORANGE_ACCENT_400,
                                on_change=on_ry,
                                on_change_end=on_ry_end,
                            ),
                        ],
                        spacing=3,
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                "Soft", size=10, color=ft.Colors.WHITE_70, width=28
                            ),
                            ft.Slider(
                                min=0.01,
                                max=0.99,
                                value=state["rad_feather"],
                                expand=True,
                                active_color=ft.Colors.ORANGE_ACCENT_400,
                                on_change=on_rf,
                                on_change_end=on_rf_end,
                            ),
                            ft.Text(
                                "Angle", size=10, color=ft.Colors.WHITE_70, width=32
                            ),
                            ft.Slider(
                                min=0,
                                max=360,
                                value=state["rad_rot"],
                                expand=True,
                                active_color=ft.Colors.ORANGE_ACCENT_400,
                                on_change=on_rot,
                                on_change_end=on_rot_end,
                            ),
                        ],
                        spacing=3,
                    ),
                ],
                spacing=2,
            )

        elif tool == "linear":
            # Linear: Size removed! Controlled by center, Feather & Rotation
            deg_val_text = ft.Text(
                f"{int(round(state['lin_deg']))}°",
                size=10,
                color=ft.Colors.ORANGE_ACCENT_200,
            )

            def throttle_linear_fast():
                now = time.perf_counter()
                if now - last_refresh_time[0] >= 0.033:
                    last_refresh_time[0] = now
                    apply_linear(fast=True)

            def on_lf(e):
                state["lin_feather"] = float(e.control.value)
                throttle_linear_fast()

            def on_lf_end(e):
                state["lin_feather"] = float(e.control.value)
                apply_linear(fast=False)

            def on_deg(e):
                state["lin_deg"] = float(e.control.value)
                deg_val_text.value = f"{int(round(state['lin_deg']))}°"
                try:
                    deg_val_text.update()
                except Exception:
                    pass
                throttle_linear_fast()

            def on_deg_end(e):
                state["lin_deg"] = float(e.control.value)
                deg_val_text.value = f"{int(round(state['lin_deg']))}°"
                try:
                    deg_val_text.update()
                except Exception:
                    pass
                apply_linear(fast=False)

            def set_preset_deg(deg: float):
                state["lin_deg"] = deg
                deg_val_text.value = f"{int(round(deg))}°"
                apply_linear(fast=False)
                rebuild_tool_options()

            def mk_preset(label: str, deg: float):
                is_sel = abs(state["lin_deg"] - deg) < 5.0
                return ft.Container(
                    content=ft.Text(
                        label,
                        size=9,
                        color=ft.Colors.WHITE if is_sel else ft.Colors.WHITE_70,
                    ),
                    padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                    bgcolor=ft.Colors.ORANGE_ACCENT_700 if is_sel else "#1A2234",
                    border_radius=ft.BorderRadius.all(6),
                    on_click=lambda ev, d=deg: set_preset_deg(d),
                )

            tool_options_container.content = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.GRADIENT,
                                size=13,
                                color=ft.Colors.ORANGE_ACCENT_400,
                            ),
                            ft.Text(
                                "Linear Gradient",
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Text(
                                "• Tap/drag to place", size=9, color=ft.Colors.WHITE_54
                            ),
                            ft.Container(expand=True),
                            mk_preset("0", 0.0),
                            mk_preset("90", 90.0),
                            mk_preset("180", 180.0),
                            mk_preset("270", 270.0),
                            deg_val_text,
                        ],
                        spacing=3,
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                "Feather", size=10, color=ft.Colors.WHITE_70, width=50
                            ),
                            ft.Slider(
                                min=0.05,
                                max=0.95,
                                value=state["lin_feather"],
                                expand=True,
                                active_color=ft.Colors.ORANGE_ACCENT_400,
                                on_change=on_lf,
                                on_change_end=on_lf_end,
                            ),
                        ],
                        spacing=3,
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                "Rotation", size=10, color=ft.Colors.WHITE_70, width=50
                            ),
                            ft.Slider(
                                min=0,
                                max=360,
                                value=state["lin_deg"],
                                expand=True,
                                active_color=ft.Colors.ORANGE_ACCENT_400,
                                on_change=on_deg,
                                on_change_end=on_deg_end,
                            ),
                        ],
                        spacing=3,
                    ),
                ],
                spacing=2,
            )

        elif tool == "color":
            # Color Tool with Color Picker + Swatches + Hue scrub
            def on_tol(e):
                state["col_tol"] = float(e.control.value)
                if state["col_rgb"]:
                    apply_color_range()

            def set_color(rgb_tuple):
                state["col_rgb"] = rgb_tuple
                apply_color_range()
                rebuild_tool_options()

            sample_hex = (
                f"#{state['col_rgb'][0]:02x}{state['col_rgb'][1]:02x}{state['col_rgb'][2]:02x}"
                if state["col_rgb"]
                else "#888888"
            )
            sample_box = ft.Container(
                width=18,
                height=18,
                bgcolor=sample_hex,
                border_radius=ft.BorderRadius.all(4),
                border=ft.Border.all(1.5, ft.Colors.WHITE),
            )

            PRESET_COLORS = [
                ("Red", (235, 50, 50)),
                ("Orange", (255, 140, 0)),
                ("Yellow", (250, 210, 20)),
                ("Green", (46, 204, 113)),
                ("Cyan", (0, 188, 212)),
                ("Blue", (41, 128, 185)),
                ("Purple", (155, 89, 182)),
                ("Magenta", (233, 30, 99)),
                ("Skin", (245, 205, 175)),
                ("Tan", (185, 120, 75)),
                ("White", (250, 250, 250)),
                ("Gray", (128, 128, 128)),
                ("Black", (25, 25, 25)),
            ]

            swatches_row = ft.Row(
                controls=[
                    ft.Container(
                        width=20,
                        height=20,
                        bgcolor=f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}",
                        border_radius=ft.BorderRadius.all(4),
                        border=ft.Border.all(1, ft.Colors.WHITE_38),
                        tooltip=name,
                        on_click=lambda ev, rgb=c: set_color(rgb),
                    )
                    for name, c in PRESET_COLORS
                ],
                spacing=5,
                scroll=ft.ScrollMode.HIDDEN,
            )

            tool_options_container.content = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.COLORIZE,
                                size=13,
                                color=ft.Colors.ORANGE_ACCENT_400,
                            ),
                            ft.Text(
                                "Color Mask",
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Text(
                                "• Tap image or pick color",
                                size=9,
                                color=ft.Colors.WHITE_54,
                                expand=True,
                            ),
                            sample_box,
                        ],
                        spacing=6,
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                "Tolerance", size=10, color=ft.Colors.WHITE_70, width=54
                            ),
                            ft.Slider(
                                min=0.05,
                                max=0.75,
                                value=state["col_tol"],
                                expand=True,
                                active_color=ft.Colors.ORANGE_ACCENT_400,
                                on_change=on_tol,
                            ),
                        ],
                        spacing=3,
                    ),
                    swatches_row,
                ],
                spacing=2,
            )

        try:
            tool_options_container.update()
        except Exception:
            pass

    # ============================================================
    # Tool bar (Bottom)
    # ============================================================
    tool_btn_map: dict[str, ft.Container] = {}

    def set_tool(tool: str):
        if tool != state["tool"]:
            # Switching tools cleans up the mask buffer as requested
            im_buf.fill(0.0)
            fast_im_buf.fill(0.0)
            stroke_pts.clear()
            state["tool"] = tool
            refresh_canvas(fast=False)
        else:
            state["tool"] = tool

        for t, btn in tool_btn_map.items():
            btn.bgcolor = (
                ft.Colors.ORANGE_ACCENT_700 if t == tool else ft.Colors.TRANSPARENT
            )
            try:
                btn.update()
            except Exception:
                pass
        # Do NOT auto-apply: user taps or drags canvas to add mask
        rebuild_tool_options()

    TOOLS = [
        ("brush", ft.Icons.BRUSH, "Brush"),
        ("eraser", ft.Icons.AUTO_FIX_NORMAL, "Erase"),
        ("radial", ft.Icons.RADIO_BUTTON_CHECKED, "Radial"),
        ("linear", ft.Icons.GRADIENT, "Linear"),
        ("color", ft.Icons.COLORIZE, "Color"),
    ]

    for t_key, t_icon, t_tip in TOOLS:
        tool_btn_map[t_key] = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(t_icon, size=20, color=ft.Colors.WHITE),
                    ft.Text(t_tip, size=9, color=ft.Colors.WHITE_70),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
            ),
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            bgcolor=(
                ft.Colors.ORANGE_ACCENT_700
                if t_key == state["tool"]
                else ft.Colors.TRANSPARENT
            ),
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
        idx = project.layers.index(layer)
        project.invalidate_cache(idx)
        project.selected_layer = layer
        app.active_mask_layer = None
        project.save()
        await page.push_route("/editor")

    # ============================================================
    # Compose layout + initialize
    # ============================================================
    rebuild_mask_list()
    rebuild_tool_options()

    appbar_title = ft.Text(
        f"Mask: {project.layers[state['main_idx']].name}",
        size=15,
        weight=ft.FontWeight.BOLD,
    )

    canvas_stack = ft.Stack(
        controls=[
            gesture_canvas,
            mask_panel,
        ],
        expand=True,
    )

    return ft.View(
        route="/editor/selector",
        bgcolor="#0B0F17",
        appbar=ft.AppBar(
            bgcolor="#111521",
            title=appbar_title,
            actions=[
                panel_toggle_btn,
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
                        canvas_stack,
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
        return (
            np.ones((ph, pw), dtype=np.float32)
            if mi == 0
            else np.zeros((ph, pw), dtype=np.float32)
        )
    if si == -1:
        return _safe_at(layer.mask, ph, pw).copy()
    if 0 <= si < len(layer.mask.sub_masks):
        return _safe_at(layer.mask.sub_masks[si], ph, pw).copy()
    return np.zeros((ph, pw), dtype=np.float32)


def _apply_stroke_feather(
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


def get_mask_icon(mask_type: str):
    return {
        "global": ft.Icons.PUBLIC,
        "brush": ft.Icons.BRUSH,
        "radial": ft.Icons.RADIO_BUTTON_CHECKED,
        "linear": ft.Icons.GRADIENT,
        "color": ft.Icons.COLORIZE,
        "luminance": ft.Icons.BRIGHTNESS_6,
    }.get(mask_type, ft.Icons.LAYERS)
