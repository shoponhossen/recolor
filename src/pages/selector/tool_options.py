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
        def on_opacity_change(e):
            state["rad_opacity"] = float(e.control.value)
            apply_radial(fast=False)

        def toggle_invert():
            state["rad_invert"] = not state.get("rad_invert", False)
            apply_radial(fast=False)
            rebuild()

        is_inv = state.get("rad_invert", False)

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
                            "Radial Gradient",
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                        ft.Text(
                            "• Drag to create & edit on canvas",
                            size=9,
                            color=ft.Colors.WHITE_54,
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.SWAP_HORIZ,
                                        size=11,
                                        color=ft.Colors.WHITE if is_inv else ft.Colors.WHITE_70,
                                    ),
                                    ft.Text(
                                        "Invert",
                                        size=9,
                                        color=ft.Colors.WHITE if is_inv else ft.Colors.WHITE_70,
                                    ),
                                ],
                                spacing=2,
                            ),
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                            bgcolor=ft.Colors.ORANGE_ACCENT_700 if is_inv else "#1A2234",
                            border_radius=ft.BorderRadius.all(5),
                            on_click=lambda ev: toggle_invert(),
                        ),
                    ],
                    spacing=4,
                ),
                ft.Row(
                    [
                        ft.Text("Opacity", size=10, color=ft.Colors.WHITE_70, width=42),
                        ft.Slider(
                            min=0.05,
                            max=1.0,
                            value=state.get("rad_opacity", 1.0),
                            expand=True,
                            active_color=ft.Colors.ORANGE_ACCENT_400,
                            on_change=on_opacity_change,
                        ),
                    ],
                    spacing=3,
                ),
            ],
            spacing=1,
        )

    elif tool == "linear":
        def on_opacity_change(e):
            state["lin_opacity"] = float(e.control.value)
            apply_linear(fast=False)

        def toggle_invert():
            state["lin_invert"] = not state.get("lin_invert", False)
            apply_linear(fast=False)
            rebuild()

        is_inv = state.get("lin_invert", False)

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
                            "Linear Gradient",
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                        ft.Text(
                            "• Drag to create & edit on canvas",
                            size=9,
                            color=ft.Colors.WHITE_54,
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.SWAP_HORIZ,
                                        size=11,
                                        color=ft.Colors.WHITE if is_inv else ft.Colors.WHITE_70,
                                    ),
                                    ft.Text(
                                        "Invert",
                                        size=9,
                                        color=ft.Colors.WHITE if is_inv else ft.Colors.WHITE_70,
                                    ),
                                ],
                                spacing=2,
                            ),
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                            bgcolor=ft.Colors.ORANGE_ACCENT_700 if is_inv else "#1A2234",
                            border_radius=ft.BorderRadius.all(5),
                            on_click=lambda ev: toggle_invert(),
                        ),
                    ],
                    spacing=4,
                ),
                ft.Row(
                    [
                        ft.Text("Opacity", size=10, color=ft.Colors.WHITE_70, width=42),
                        ft.Slider(
                            min=0.05,
                            max=1.0,
                            value=state.get("lin_opacity", 1.0),
                            expand=True,
                            active_color=ft.Colors.ORANGE_ACCENT_400,
                            on_change=on_opacity_change,
                        ),
                    ],
                    spacing=3,
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
