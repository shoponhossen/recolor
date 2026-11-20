import flet as ft
from .constants import PRESET_COLORS


def build_tool_options(
    container: ft.Container,
    state: dict,
    callbacks: dict,
    prev_w: int,
    prev_h: int,
):
    """Rebuild the active tool settings panel (Brush, Radial, Linear, Color)."""
    tool = state["tool"]
    rebuild = callbacks["rebuild"]
    apply_radial = callbacks["apply_radial"]
    apply_linear = callbacks["apply_linear"]
    apply_color = callbacks["apply_color"]
    throttle_radial = callbacks.get("throttle_radial")
    throttle_linear = callbacks.get("throttle_linear")

    if tool == "brush":

        def on_sz(e):
            state["brush_sz"] = float(e.control.value)

        def on_fth(e):
            state["feather"] = float(e.control.value)

        def set_mode(m: str):
            state["brush_mode"] = m
            rebuild()

        is_paint = state["brush_mode"] == "paint"

        container.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.BRUSH,
                            size=13,
                            color=ft.Colors.ORANGE_ACCENT_400,
                        ),
                        ft.Text(
                            "Brush",
                            size=11,
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Container(expand=True),
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.BRUSH,
                                        size=11,
                                        color=ft.Colors.WHITE if is_paint else ft.Colors.WHITE_70,
                                    ),
                                    ft.Text(
                                        "Paint",
                                        size=10,
                                        color=ft.Colors.WHITE if is_paint else ft.Colors.WHITE_70,
                                    ),
                                ],
                                spacing=2,
                            ),
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                            bgcolor=ft.Colors.GREEN_700 if is_paint else "#1A2234",
                            border_radius=ft.BorderRadius.all(5),
                            on_click=lambda ev: set_mode("paint"),
                        ),
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.AUTO_FIX_NORMAL,
                                        size=11,
                                        color=ft.Colors.WHITE if not is_paint else ft.Colors.WHITE_70,
                                    ),
                                    ft.Text(
                                        "Erase",
                                        size=10,
                                        color=ft.Colors.WHITE if not is_paint else ft.Colors.WHITE_70,
                                    ),
                                ],
                                spacing=2,
                            ),
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                            bgcolor=ft.Colors.RED_700 if not is_paint else "#1A2234",
                            border_radius=ft.BorderRadius.all(5),
                            on_click=lambda ev: set_mode("erase"),
                        ),
                    ],
                    spacing=5,
                ),
                ft.Row(
                    [
                        ft.Text("Size", size=10, color=ft.Colors.WHITE_70, width=24),
                        ft.Slider(
                            min=5,
                            max=150,
                            value=state["brush_sz"],
                            expand=True,
                            active_color=ft.Colors.ORANGE_ACCENT_400,
                            on_change=on_sz,
                        ),
                        ft.Text("Soft", size=10, color=ft.Colors.WHITE_70, width=24),
                        ft.Slider(
                            min=0,
                            max=1,
                            value=state["feather"],
                            expand=True,
                            active_color=ft.Colors.ORANGE_ACCENT_400,
                            on_change=on_fth,
                        ),
                    ],
                    spacing=3,
                ),
            ],
            spacing=1,
        )

    elif tool == "radial":
        rot_val_text = ft.Text(
            f"{int(round(state['rad_rot']))}°",
            size=10,
            color=ft.Colors.ORANGE_ACCENT_200,
        )

        def on_rx(e):
            state["rad_width"] = float(e.control.value)
            if throttle_radial:
                throttle_radial()

        def on_rx_end(e):
            state["rad_width"] = float(e.control.value)
            apply_radial(fast=False)

        def on_ry(e):
            state["rad_height"] = float(e.control.value)
            if throttle_radial:
                throttle_radial()

        def on_ry_end(e):
            state["rad_height"] = float(e.control.value)
            apply_radial(fast=False)

        def on_rf(e):
            state["rad_feather"] = float(e.control.value)
            if throttle_radial:
                throttle_radial()

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
            if throttle_radial:
                throttle_radial()

        def on_rot_end(e):
            state["rad_rot"] = float(e.control.value)
            rot_val_text.value = f"{int(round(state['rad_rot']))}°"
            try:
                rot_val_text.update()
            except Exception:
                pass
            apply_radial(fast=False)

        container.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.RADIO_BUTTON_CHECKED,
                            size=13,
                            color=ft.Colors.ORANGE_ACCENT_400,
                        ),
                        ft.Text(
                            "Radial",
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                        ft.Text(
                            "• Drag canvas to place",
                            size=9,
                            color=ft.Colors.WHITE_54,
                            expand=True,
                        ),
                        ft.Text("Rot:", size=10, color=ft.Colors.WHITE_70),
                        rot_val_text,
                    ],
                    spacing=3,
                ),
                ft.Row(
                    [
                        ft.Text("W", size=10, color=ft.Colors.WHITE_70, width=14),
                        ft.Slider(
                            min=10,
                            max=prev_w * 1.5,
                            value=state["rad_width"],
                            expand=True,
                            active_color=ft.Colors.ORANGE_ACCENT_400,
                            on_change=on_rx,
                            on_change_end=on_rx_end,
                        ),
                        ft.Text("H", size=10, color=ft.Colors.WHITE_70, width=14),
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
                    spacing=2,
                ),
                ft.Row(
                    [
                        ft.Text("Soft", size=10, color=ft.Colors.WHITE_70, width=24),
                        ft.Slider(
                            min=0.01,
                            max=0.99,
                            value=state["rad_feather"],
                            expand=True,
                            active_color=ft.Colors.ORANGE_ACCENT_400,
                            on_change=on_rf,
                            on_change_end=on_rf_end,
                        ),
                        ft.Text("Angle", size=10, color=ft.Colors.WHITE_70, width=28),
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
                    spacing=2,
                ),
            ],
            spacing=1,
        )

    elif tool == "linear":
        deg_val_text = ft.Text(
            f"{int(round(state['lin_deg']))}°",
            size=10,
            color=ft.Colors.ORANGE_ACCENT_200,
        )

        def on_lf(e):
            state["lin_feather"] = float(e.control.value)
            if throttle_linear:
                throttle_linear()

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
            if throttle_linear:
                throttle_linear()

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
            rebuild()

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

        container.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.GRADIENT,
                            size=13,
                            color=ft.Colors.ORANGE_ACCENT_400,
                        ),
                        ft.Text(
                            "Linear",
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                        ft.Container(expand=True),
                        mk_preset("Bottom", 270.0),
                        mk_preset("Top", 90.0),
                        mk_preset("Right", 180.0),
                        mk_preset("Left", 0.0),
                        deg_val_text,
                    ],
                    spacing=3,
                ),
                ft.Row(
                    [
                        ft.Text("Soft", size=10, color=ft.Colors.WHITE_70, width=24),
                        ft.Slider(
                            min=0.05,
                            max=0.95,
                            value=state["lin_feather"],
                            expand=True,
                            active_color=ft.Colors.ORANGE_ACCENT_400,
                            on_change=on_lf,
                            on_change_end=on_lf_end,
                        ),
                        ft.Text("Angle", size=10, color=ft.Colors.WHITE_70, width=28),
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
                    spacing=2,
                ),
            ],
            spacing=1,
        )

    elif tool == "color":

        def on_tol(e):
            state["col_tol"] = float(e.control.value)
            if state["col_rgb"]:
                apply_color()

        def set_color(rgb_tuple):
            state["col_rgb"] = rgb_tuple
            apply_color()
            rebuild()

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
            scroll=ft.ScrollMode.AUTO,
        )

        container.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.COLORIZE,
                            size=13,
                            color=ft.Colors.ORANGE_ACCENT_400,
                        ),
                        ft.Text(
                            "Color",
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                        sample_box,
                        ft.Text("Tol", size=10, color=ft.Colors.WHITE_70, width=20),
                        ft.Slider(
                            min=0.05,
                            max=0.75,
                            value=state["col_tol"],
                            expand=True,
                            active_color=ft.Colors.ORANGE_ACCENT_400,
                            on_change=on_tol,
                        ),
                    ],
                    spacing=4,
                ),
                swatches_row,
            ],
            spacing=1,
        )

    try:
        container.update()
    except Exception:
        pass
