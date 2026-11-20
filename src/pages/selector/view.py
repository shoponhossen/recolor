import flet as ft
import numpy as np
import cv2
import time
from app import ReColor
from utils import get_default_sample_path
from .constants import TOOLS, get_mask_icon
from .helpers import (
    safe_at,
    load_target_buf,
    apply_stroke_feather,
    map_coords_to_img,
)
from .generators import (
    generate_radial_mask,
    generate_linear_mask,
    generate_color_range_mask,
)
from .renderer import render_mask_canvas
from .tool_options import build_tool_options
from .mask_panel import (
    show_alert,
    on_export_mask_image,
    on_import_mask_image,
    on_rename_layer,
    show_parent_options,
    show_child_options,
    render_mask_list_column,
)


def selector_view(page: ft.Page, app: ReColor) -> ft.View:
    page.overlay.clear()
    pm = app.projects_manager

    if pm.project is None:
        pm.create_project("Default", get_default_sample_path())

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

    # Fast low-res preview buffer (<= 360px max side) for smooth interaction
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

    # State
    state = {
        "main_idx": project.layers.index(init_layer),
        "sub_idx": -1,
        "tool": "brush",
        "brush_sz": 28.0,
        "feather": 0.3,
        "brush_mode": "paint",
        "rad_cx": prev_w / 2.0,
        "rad_cy": prev_h / 2.0,
        "rad_width": prev_w * 0.35,
        "rad_height": prev_h * 0.35,
        "rad_feather": 0.5,
        "rad_rot": 0.0,
        "lin_cx": prev_w / 2.0,
        "lin_cy": prev_h / 2.0,
        "lin_feather": 0.5,
        "lin_deg": 270.0,
        "col_rgb": None,
        "col_tol": 0.35,
    }

    viewport = [360.0, 420.0]
    im_buf: np.ndarray = load_target_buf(
        project, state["main_idx"], state["sub_idx"], prev_h, prev_w
    )
    cv2.resize(im_buf, (fast_w, fast_h), dst=fast_im_buf, interpolation=cv2.INTER_LINEAR)

    stroke_pts: list[tuple[float, float]] = []
    last_refresh_time = [0.0]
    panel_visible = [True]

    def to_img(x: float, y: float) -> tuple[float, float]:
        return map_coords_to_img(x, y, viewport, prev_w, prev_h)

    def render_canvas(fast: bool = False) -> bytes:
        return render_mask_canvas(
            project=project,
            state=state,
            im_buf=im_buf,
            fast_im_buf=fast_im_buf,
            prev_arr=prev_arr,
            fast_prev_arr=fast_prev_arr,
            prev_w=prev_w,
            prev_h=prev_h,
            fast_w=fast_w,
            fast_h=fast_h,
            fast=fast,
        )

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

    mask_list_col = ft.Column(spacing=5, scroll=ft.ScrollMode.AUTO)

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
        border_radius=ft.BorderRadius.only(top_left=8, bottom_left=8),
        padding=ft.Padding.symmetric(horizontal=4, vertical=4),
        visible=panel_visible[0],
    )

    def update_mask_panel_layout():
        mask_panel.right = 0
        mask_panel.top = 0
        mask_panel.bottom = 0
        try:
            mask_panel.update()
        except Exception:
            pass

    def on_canvas_size(e):
        vw = float(e.width or 360)
        vh = float(e.height or 420)
        viewport[0] = vw
        viewport[1] = vh
        update_mask_panel_layout()

    # Procedural mask applications
    def apply_radial(fast: bool = False):
        if fast:
            grad = generate_radial_mask(
                cx=state["rad_cx"] * fast_scale,
                cy=state["rad_cy"] * fast_scale,
                rx=state["rad_width"] * fast_scale,
                ry=state["rad_height"] * fast_scale,
                feather=state["rad_feather"],
                deg=state["rad_rot"],
                x_grid=fast_x_grid,
                y_grid=fast_y_grid,
            )
            np.copyto(fast_im_buf, grad)
            refresh_canvas(fast=True)
        else:
            grad = generate_radial_mask(
                cx=state["rad_cx"],
                cy=state["rad_cy"],
                rx=state["rad_width"],
                ry=state["rad_height"],
                feather=state["rad_feather"],
                deg=state["rad_rot"],
                x_grid=x_grid,
                y_grid=y_grid,
            )
            np.copyto(im_buf, grad)
            cv2.resize(im_buf, (fast_w, fast_h), dst=fast_im_buf, interpolation=cv2.INTER_LINEAR)
            refresh_canvas(fast=False)

    def apply_linear(fast: bool = False):
        if fast:
            t = generate_linear_mask(
                cx=state["lin_cx"] * fast_scale,
                cy=state["lin_cy"] * fast_scale,
                feather=state["lin_feather"],
                deg=state["lin_deg"],
                x_grid=fast_x_grid,
                y_grid=fast_y_grid,
                span_base=min(fast_w, fast_h) * 0.7,
            )
            np.copyto(fast_im_buf, t)
            refresh_canvas(fast=True)
        else:
            t = generate_linear_mask(
                cx=state["lin_cx"],
                cy=state["lin_cy"],
                feather=state["lin_feather"],
                deg=state["lin_deg"],
                x_grid=x_grid,
                y_grid=y_grid,
                span_base=min(prev_w, prev_h) * 0.7,
            )
            np.copyto(im_buf, t)
            cv2.resize(im_buf, (fast_w, fast_h), dst=fast_im_buf, interpolation=cv2.INTER_LINEAR)
            refresh_canvas(fast=False)

    def apply_color_range():
        if state["col_rgb"] is None:
            return
        new_mask = generate_color_range_mask(
            rgb_img=prev_arr,
            target_rgb=state["col_rgb"],
            tolerance=state["col_tol"],
        )
        np.copyto(im_buf, new_mask)
        cv2.resize(im_buf, (fast_w, fast_h), dst=fast_im_buf, interpolation=cv2.INTER_LINEAR)
        refresh_canvas(fast=False)

    # Touch / Drag Handlers
    def on_pan_start(e: ft.DragStartEvent):
        tool = state["tool"]
        ix, iy = to_img(e.local_position.x, e.local_position.y)

        if tool == "brush":
            stroke_pts.clear()
            stroke_pts.append((ix, iy))
            color = 0.0 if state["brush_mode"] == "erase" else 1.0
            r = max(1, int(round(state["brush_sz"] / 2.0)))
            cv2.circle(im_buf, (int(round(ix)), int(round(iy))), r, color, -1, cv2.LINE_AA)
            cv2.circle(
                fast_im_buf,
                (int(round(ix * fast_scale)), int(round(iy * fast_scale))),
                max(1, int(round(r * fast_scale))),
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

        if tool == "brush":
            color = 0.0 if state["brush_mode"] == "erase" else 1.0
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
            cv2.circle(im_buf, (int(round(ix)), int(round(iy))), r, color, -1, cv2.LINE_AA)
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
            if now - last_refresh_time[0] >= 0.033:
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
        if tool == "brush":
            if state["feather"] > 0.05 and stroke_pts:
                apply_stroke_feather(
                    im_buf, stroke_pts, state["brush_sz"], state["feather"], prev_h, prev_w
                )
            stroke_pts.clear()
            cv2.resize(im_buf, (fast_w, fast_h), dst=fast_im_buf, interpolation=cv2.INTER_LINEAR)
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
            state["rad_cx"] = ix
            state["rad_cy"] = iy
            apply_radial(fast=False)
        elif tool == "linear":
            state["lin_cx"] = ix
            state["lin_cy"] = iy
            apply_linear(fast=False)

    gesture_canvas = ft.GestureDetector(
        content=ft.Container(
            content=img_disp,
            alignment=ft.Alignment.CENTER,
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

    # Persistence & Layer Switch
    def save_buf():
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
        nonlocal im_buf, fast_im_buf
        im_buf = load_target_buf(project, mi, si, prev_h, prev_w)
        cv2.resize(im_buf, (fast_w, fast_h), dst=fast_im_buf, interpolation=cv2.INTER_LINEAR)

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
        save_buf()
        new_layer = project.add_layer(mask_type="brush")
        mi = project.layers.index(new_layer)
        switch_to(mi, -1)

    def on_add_sub(li: int, mode: str):
        save_buf()
        layer = project.layers[li]
        layer.mask.add_sub_mask(mode=mode, mask_type="brush", size=(prev_h, prev_w))
        si_new = len(layer.mask.sub_masks) - 1
        state["tool"] = "brush"
        switch_to(li, si_new)

    def toggle_vis(layer):
        layer.visible = not layer.visible
        rebuild_mask_list()

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

    def on_dup_layer(li: int):
        save_buf()
        dup = project.duplicate_layer(project.layers[li])
        mi = project.layers.index(dup)
        switch_to(mi, -1)

    def op_invert():
        np.copyto(im_buf, np.clip(1.0 - im_buf, 0.0, 1.0))
        cv2.resize(im_buf, (fast_w, fast_h), dst=fast_im_buf, interpolation=cv2.INTER_LINEAR)
        refresh_canvas(fast=False)

    def op_fill():
        im_buf.fill(1.0)
        fast_im_buf.fill(1.0)
        refresh_canvas(fast=False)

    # Panel Handlers bundle
    panel_handlers = {
        "save_buf": save_buf,
        "switch_to": switch_to,
        "add_main": on_add_main_mask,
        "add_sub": on_add_sub,
        "toggle_vis": toggle_vis,
        "delete": on_delete_layer,
        "duplicate": on_dup_layer,
        "invert": op_invert,
        "fill": op_fill,
        "rename": lambda li: on_rename_layer(page, project, li, appbar_title, rebuild_mask_list),
        "export": lambda li: on_export_mask_image(page, project, li, save_buf),
        "import": lambda li: page.run_task(
            on_import_mask_image,
            page,
            app,
            project,
            state,
            im_buf,
            fast_im_buf,
            prev_w,
            prev_h,
            fast_w,
            fast_h,
            refresh_canvas,
            rebuild_mask_list,
            li,
        ),
        "show_parent_opts": lambda li: show_parent_options(page, project, li, panel_handlers),
        "show_child_opts": lambda li, si: show_child_options(page, project, li, si, panel_handlers),
    }

    def rebuild_mask_list():
        render_mask_list_column(mask_list_col, project, state, panel_handlers)
        update_mask_panel_layout()

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

    # Tool options container
    tool_options_container = ft.Container(
        bgcolor="#111521",
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        height=78,
    )

    def throttle_radial_fast():
        now = time.perf_counter()
        if now - last_refresh_time[0] >= 0.033:
            last_refresh_time[0] = now
            apply_radial(fast=True)

    def throttle_linear_fast():
        now = time.perf_counter()
        if now - last_refresh_time[0] >= 0.033:
            last_refresh_time[0] = now
            apply_linear(fast=True)

    tool_callbacks = {
        "rebuild": lambda: rebuild_tool_options(),
        "apply_radial": apply_radial,
        "apply_linear": apply_linear,
        "apply_color": apply_color_range,
        "throttle_radial": throttle_radial_fast,
        "throttle_linear": throttle_linear_fast,
    }

    def rebuild_tool_options():
        build_tool_options(tool_options_container, state, tool_callbacks, prev_w, prev_h)

    # Tool navigation bar
    tool_btn_map: dict[str, ft.Container] = {}

    def set_tool(tool: str):
        if tool != state["tool"]:
            if tool != "brush" and state["tool"] != "brush":
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

        rebuild_tool_options()

    for t_key, t_icon, t_tip in TOOLS:
        tool_btn_map[t_key] = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(t_icon, size=18, color=ft.Colors.WHITE),
                    ft.Text(t_tip, size=9, color=ft.Colors.WHITE_70),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
            ),
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
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
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.MainAxisAlignment.START,
            spacing=4,
        ),
        bgcolor="#161B26",
        padding=ft.Padding.symmetric(horizontal=6, vertical=5),
    )

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

    async def go_back(e):
        save_buf()
        app.active_mask_layer = None
        project.save()
        await page.push_route("/editor")

    # Initial view composition
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
            leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=go_back),
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
