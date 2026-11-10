import flet as ft
from app import ReColor, ProjectManager, Project
from utils import arr_to_jpeg_bytes
from components.slider import CenterSlider
from backend.backend import (
    ADJUSTMENTS_LIST,
    ADJUSTMENTS_BY_CATEGORY,
    CATEGORIES,
    Layer,
)


def editor_view(page: ft.Page, app: ReColor) -> ft.View:
    page.overlay.clear()
    pm: ProjectManager = app.projects_manager

    if pm.project is None:
        pm.create_project("Default", r"D:\Projects\recolor\default.jpg")

    project: Project = pm.project

    if project.selected_layer is None or project.selected_layer not in project.layers:
        if not project.layers:
            project.add_layer("Global", "global")
        project.selected_layer = project.layers[0]

    # === State ===
    is_comparing = False
    is_adjusting = False
    active_category = "Light"
    active_adj_key = ADJUSTMENTS_BY_CATEGORY["Light"][0].key  # "exposure"
    layer_dropdown_open = False

    # === Helpers ===

    def get_preview_bytes() -> bytes:
        if is_comparing:
            return arr_to_jpeg_bytes(project.preview_image_array, quality=85)
        return arr_to_jpeg_bytes(project.render_preview(dirty=0), quality=85)

    def get_mask_icon(mask_type: str):
        return {
            "global": ft.Icons.PUBLIC,
            "brush": ft.Icons.BRUSH,
            "radial": ft.Icons.RADIO_BUTTON_CHECKED,
            "linear": ft.Icons.GRADIENT,
            "color": ft.Icons.COLORIZE,
            "luminance": ft.Icons.BRIGHTNESS_6,
        }.get(mask_type, ft.Icons.LAYERS)

    def fmt_val(v: float) -> str:
        iv = int(round(v))
        return f"+{iv}" if iv > 0 else str(iv)

    # === Canvas image ===

    img_control = ft.Image(
        src=get_preview_bytes(),
        fit=ft.BoxFit.CONTAIN,
        expand=True,
        gapless_playback=True,
    )

    def refresh_image(dirty: int = 0):
        if is_comparing:
            img_control.src = arr_to_jpeg_bytes(project.preview_image_array, quality=85)
        else:
            preview = project.render_preview(dirty=dirty)
            img_control.src = arr_to_jpeg_bytes(preview, quality=80)
        try:
            img_control.update()
        except Exception:
            pass

    # === Layer Overlay Dropdown (bottom-right of canvas) ===

    layer_chip_icon = ft.Icon(ft.Icons.PUBLIC, size=14, color=ft.Colors.WHITE)
    layer_chip_text = ft.Text("", size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600)
    layer_chip_arrow = ft.Icon(ft.Icons.EXPAND_LESS, size=14, color=ft.Colors.WHITE_70)

    layer_dropdown_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO)

    layer_dropdown_panel = ft.Container(
        content=layer_dropdown_col,
        bgcolor=ft.Colors.with_opacity(0.96, "#111521"),
        border_radius=ft.BorderRadius.all(10),
        padding=ft.Padding.all(8),
        right=4,
        bottom=42,
        visible=False,
        width=190,
        height=220,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.WHITE)),
    )

    layer_chip = ft.Container(
        content=ft.Row(
            controls=[layer_chip_icon, layer_chip_text, layer_chip_arrow],
            spacing=5,
        ),
        bgcolor=ft.Colors.with_opacity(0.85, "#111521"),
        border_radius=ft.BorderRadius.all(14),
        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
        right=4,
        bottom=4,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
        on_click=lambda e: toggle_dropdown(),
    )

    def toggle_dropdown():
        nonlocal layer_dropdown_open
        layer_dropdown_open = not layer_dropdown_open
        layer_dropdown_panel.visible = layer_dropdown_open
        layer_chip_arrow.name = (
            ft.Icons.EXPAND_LESS if layer_dropdown_open else ft.Icons.EXPAND_MORE
        )
        rebuild_layer_dropdown()
        try:
            layer_dropdown_panel.update()
            layer_chip_arrow.update()
        except Exception:
            pass

    def sync_layer_chip():
        layer = project.selected_layer
        if layer:
            layer_chip_icon.name = get_mask_icon(layer.mask_type)
            layer_chip_text.value = layer.name[:14]
        try:
            layer_chip_icon.update()
            layer_chip_text.update()
        except Exception:
            pass

    def rebuild_layer_dropdown():
        layer_dropdown_col.controls.clear()
        for layer in project.layers:
            is_sel = layer == project.selected_layer
            sub_count = len(layer.mask.sub_masks) if layer.mask else 0

            def on_select_layer(ev, l=layer):
                project.selected_layer = l
                sync_layer_chip()
                sync_slider_to_active()
                rebuild_adj_cards()
                rebuild_layer_dropdown()
                refresh_image()

            async def on_edit_mask(ev, l=layer):
                toggle_dropdown()
                app.active_mask_layer = l
                project.save()
                await page.push_route("/editor/selector")

            row = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(get_mask_icon(layer.mask_type), size=14,
                                color=ft.Colors.ORANGE_ACCENT_400 if is_sel else ft.Colors.WHITE_54),
                        ft.Column([
                            ft.Text(layer.name, size=12,
                                    color=ft.Colors.WHITE if is_sel else ft.Colors.WHITE_70,
                                    weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.NORMAL),
                            ft.Text(f"{sub_count} sub-mask{'s' if sub_count != 1 else ''}" if sub_count else "no sub-masks",
                                    size=10, color=ft.Colors.WHITE_38),
                        ], spacing=0, expand=True),
                        ft.IconButton(
                            icon=ft.Icons.EDIT,
                            icon_size=14,
                            icon_color=ft.Colors.ORANGE_ACCENT_400 if is_sel else ft.Colors.WHITE_38,
                            tooltip="Edit Mask",
                            on_click=on_edit_mask,
                            width=28, height=28, padding=0,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.VISIBILITY if layer.visible else ft.Icons.VISIBILITY_OFF,
                            icon_size=14,
                            icon_color=ft.Colors.WHITE_70 if layer.visible else ft.Colors.WHITE_24,
                            on_click=lambda ev, l=layer: toggle_vis(l),
                            width=28, height=28, padding=0,
                        ),
                    ],
                    spacing=4,
                ),
                bgcolor="#1E2536" if is_sel else "transparent",
                border_radius=ft.BorderRadius.all(8),
                padding=ft.Padding.symmetric(horizontal=6, vertical=5),
                on_click=on_select_layer,
            )
            layer_dropdown_col.controls.append(row)

        try:
            layer_dropdown_col.update()
        except Exception:
            pass

    def toggle_vis(layer: Layer):
        layer.visible = not layer.visible
        idx = project.layers.index(layer)
        project.invalidate_cache(idx)
        rebuild_layer_dropdown()
        refresh_image(dirty=idx)

    sync_layer_chip()

    # === Adjustment Cards ===

    adj_cards_row_ctrl = ft.Row(
        scroll=ft.ScrollMode.ALWAYS,
        spacing=6,
    )

    # Single shared slider
    single_slider = CenterSlider(min=-100.0, max=100.0, value=0.0)

    slider_adj_name_text = ft.Text("Exposure", size=12, color=ft.Colors.WHITE_70)
    slider_val_text = ft.Text("0", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)

    slider_reset_btn = ft.IconButton(
        icon=ft.Icons.REFRESH,
        icon_size=16,
        icon_color=ft.Colors.WHITE_38,
        tooltip="Reset to 0",
        width=30, height=30, padding=0,
    )

    def sync_slider_to_active():
        if project.selected_layer:
            val = project.selected_layer.values.get(active_adj_key, 0.0)
            single_slider.set_value(val)
            iv = int(round(val))
            slider_val_text.value = f"+{iv}" if iv > 0 else str(iv)
            slider_val_text.color = (
                ft.Colors.ORANGE_ACCENT_400 if iv != 0 else ft.Colors.WHITE_54
            )
        try:
            slider_val_text.update()
        except Exception:
            pass

    def on_slider_change(val: float):
        if not project.selected_layer:
            return
        project.selected_layer.values[active_adj_key] = val
        idx = project.layers.index(project.selected_layer)
        project.invalidate_cache(idx)
        preview = project.render_preview(dirty=idx)
        img_control.src = arr_to_jpeg_bytes(preview, quality=78)

        iv = int(round(val))
        slider_val_text.value = f"+{iv}" if iv > 0 else str(iv)
        slider_val_text.color = (
            ft.Colors.ORANGE_ACCENT_400 if iv != 0 else ft.Colors.WHITE_54
        )
        try:
            img_control.update()
            slider_val_text.update()
        except Exception:
            pass

    def on_slider_start(e):
        # Hide canvas chrome during adjusting
        layer_chip.visible = False
        layer_dropdown_panel.visible = False
        try:
            layer_chip.update()
            layer_dropdown_panel.update()
        except Exception:
            pass

    def on_slider_end(val: float):
        layer_chip.visible = True
        layer_chip.visible = True
        rebuild_adj_cards()
        try:
            layer_chip.update()
        except Exception:
            pass

    single_slider.on_change = on_slider_change
    single_slider.on_change_start = on_slider_start
    single_slider.on_change_end = on_slider_end

    def on_reset_adj(e):
        if project.selected_layer:
            project.selected_layer.values[active_adj_key] = 0.0
            idx = project.layers.index(project.selected_layer)
            project.invalidate_cache(idx)
            single_slider.set_value(0.0)
            rebuild_adj_cards()
            refresh_image(dirty=idx)

    slider_reset_btn.on_click = on_reset_adj

    def select_adj(key: str):
        nonlocal active_adj_key
        active_adj_key = key
        sync_slider_to_active()
        rebuild_adj_cards()

    def rebuild_adj_cards():
        adj_cards_row_ctrl.controls.clear()
        adjs = ADJUSTMENTS_BY_CATEGORY.get(active_category, [])
        for adj in adjs:
            is_sel = adj.key == active_adj_key
            val = (
                project.selected_layer.values.get(adj.key, 0.0)
                if project.selected_layer
                else 0.0
            )
            iv = int(round(val))
            val_color = ft.Colors.ORANGE_ACCENT_400 if iv != 0 else ft.Colors.WHITE_38

            card = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            adj.name,
                            size=10,
                            color=ft.Colors.WHITE,
                            text_align=ft.TextAlign.CENTER,
                            weight=ft.FontWeight.W_600 if is_sel else ft.FontWeight.NORMAL,
                        ),
                        ft.Text(
                            f"+{iv}" if iv > 0 else str(iv),
                            size=11,
                            color=val_color,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                width=62,
                height=64,
                bgcolor="#1E2742" if is_sel else "#141824",
                border=ft.Border.all(
                    1.5 if is_sel else 1,
                    ft.Colors.ORANGE_ACCENT_400 if is_sel else ft.Colors.with_opacity(0.12, ft.Colors.WHITE),
                ),
                border_radius=ft.BorderRadius.all(10),
                alignment=ft.Alignment.CENTER,
                on_click=lambda ev, k=adj.key: select_adj(k),
            )
            adj_cards_row_ctrl.controls.append(card)

        # Also refresh slider label
        adj_obj = next((a for a in ADJUSTMENTS_LIST if a.key == active_adj_key), None)
        if adj_obj:
            slider_adj_name_text.value = adj_obj.name

        try:
            adj_cards_row_ctrl.update()
            slider_adj_name_text.update()
        except Exception:
            pass

    # === Category Bar ===

    cat_btn_map: dict[str, ft.Container] = {}

    def switch_category(cat: str):
        nonlocal active_category, active_adj_key
        active_category = cat
        adjs = ADJUSTMENTS_BY_CATEGORY.get(cat, [])
        if adjs:
            active_adj_key = adjs[0].key
        for c, btn in cat_btn_map.items():
            btn.bgcolor = ft.Colors.ORANGE_ACCENT_700 if c == cat else ft.Colors.TRANSPARENT
            try:
                btn.update()
            except Exception:
                pass
        sync_slider_to_active()
        rebuild_adj_cards()

    for cat in CATEGORIES:
        cat_btn_map[cat] = ft.Container(
            content=ft.Text(cat, size=13, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
            padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            bgcolor=ft.Colors.ORANGE_ACCENT_700 if cat == active_category else ft.Colors.TRANSPARENT,
            border_radius=ft.BorderRadius.all(8),
            on_click=lambda ev, c=cat: switch_category(c),
        )

    category_bar = ft.Container(
        content=ft.Row(
            controls=list(cat_btn_map.values()),
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
        ),
        bgcolor="#111521",
        padding=ft.Padding.symmetric(horizontal=12, vertical=4),
    )

    # === AppBar Actions ===

    compare_btn = ft.IconButton(
        icon=ft.Icons.COMPARE,
        icon_color=ft.Colors.WHITE,
        tooltip="Before/After",
    )

    def toggle_compare(e):
        nonlocal is_comparing
        is_comparing = not is_comparing
        compare_btn.icon_color = (
            ft.Colors.ORANGE_ACCENT_400 if is_comparing else ft.Colors.WHITE
        )
        try:
            compare_btn.update()
        except Exception:
            pass
        refresh_image()

    compare_btn.on_click = toggle_compare

    def reset_layer(e):
        if not project.selected_layer:
            return
        def confirm(ev):
            page.pop_dialog()
            project.selected_layer.reset_adjustments()
            idx = project.layers.index(project.selected_layer)
            project.invalidate_cache(idx)
            sync_slider_to_active()
            rebuild_adj_cards()
            refresh_image(dirty=idx)
        page.show_dialog(ft.AlertDialog(
            title=ft.Text("Reset Layer?"),
            content=ft.Text(f"Reset all adjustments on '{project.selected_layer.name}'?"),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: page.pop_dialog()),
                ft.TextButton("Reset", on_click=confirm),
            ],
        ))

    def export_image(e):
        async def do_export(fmt):
            page.pop_dialog()

            loading_dlg = ft.AlertDialog(
                modal=True,
                content=ft.Row([
                    ft.ProgressRing(color=ft.Colors.ORANGE_ACCENT_400),
                    ft.Container(width=10),
                    ft.Text("Rendering full-res image...", size=13, color=ft.Colors.WHITE),
                ], alignment=ft.MainAxisAlignment.CENTER),
                bgcolor="#151A27",
            )
            page.show_dialog(loading_dlg)

            path = project.projects_directory / f"{project.name}_export.{fmt}"
            try:
                project.export_full_image(path, quality=95)
                page.pop_dialog()  # Close loading
                page.show_dialog(ft.AlertDialog(
                    title=ft.Text("Export Complete!", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    content=ft.Text(f"Saved full resolution graded image to:\n{path}", size=12, color=ft.Colors.WHITE_70),
                    actions=[ft.Button(content="OK", on_click=lambda ev: page.pop_dialog())],
                    bgcolor="#151A27",
                ))
            except Exception as ex:
                page.pop_dialog()
                page.show_dialog(ft.AlertDialog(
                    title=ft.Text("Export Failed", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_ACCENT_400),
                    content=ft.Text(str(ex), size=12, color=ft.Colors.WHITE_70),
                    actions=[ft.Button(content="OK", on_click=lambda ev: page.pop_dialog())],
                    bgcolor="#151A27",
                ))

        page.show_dialog(ft.AlertDialog(
            title=ft.Text("Export Graded Image", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            content=ft.Text("Select export format (rendered at original camera resolution):", size=12, color=ft.Colors.WHITE_70),
            actions=[
                ft.Button(content="JPEG", on_click=lambda ev: page.run_task(do_export, "jpg")),
                ft.Button(content="PNG",  on_click=lambda ev: page.run_task(do_export, "png")),
                ft.TextButton("Cancel", on_click=lambda ev: page.pop_dialog()),
            ],
            bgcolor="#151A27",
        ))

    async def go_mask_studio(e):
        """Switch directly between Editor and Mask Studio (Selector) for the active layer."""
        app.active_mask_layer = project.selected_layer
        project.save()
        await page.push_route("/editor/selector")

    def on_save_project(e):
        project.save()
        page.show_dialog(ft.AlertDialog(
            title=ft.Text("Project Saved", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            content=ft.Text(f"Saved '{project.name}' successfully.", size=12, color=ft.Colors.WHITE_70),
            actions=[ft.Button(content="OK", on_click=lambda ev: page.pop_dialog())],
            bgcolor="#151A27",
        ))

    async def go_back(e):
        project.save()
        await page.push_route("/")

    # === Canvas Stack ===

    canvas_stack = ft.Stack(
        controls=[
            ft.Container(content=img_control, expand=True),
            layer_dropdown_panel,
            layer_chip,
        ],
        expand=True,
    )

    # === Slider Row ===

    slider_row = ft.Container(
        content=ft.Column([
            ft.Row([
                slider_adj_name_text,
                ft.Row([
                    slider_reset_btn,
                    ft.Container(
                        content=slider_val_text,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.WHITE),
                        border_radius=ft.BorderRadius.all(10),
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                    ),
                ], spacing=4),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            single_slider,
        ], spacing=2),
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        bgcolor="#0E121B",
    )

    rebuild_adj_cards()
    sync_slider_to_active()
    sync_layer_chip()

    return ft.View(
        route="/editor",
        bgcolor="#0B0F17",
        appbar=ft.AppBar(
            bgcolor="#111521",
            leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=go_back),
            title=ft.Text(project.name, size=16, weight=ft.FontWeight.BOLD),
            actions=[
                compare_btn,
                ft.IconButton(
                    ft.Icons.AUTO_FIX_HIGH,
                    tooltip="Mask Studio (Selector)",
                    icon_color=ft.Colors.ORANGE_ACCENT_400,
                    on_click=go_mask_studio,
                ),
                ft.IconButton(ft.Icons.REFRESH, tooltip="Reset Layer", on_click=reset_layer),
                ft.IconButton(ft.Icons.FILE_DOWNLOAD, tooltip="Export Image", on_click=export_image),
                ft.IconButton(ft.Icons.SAVE, tooltip="Save Project", on_click=on_save_project),
            ],
        ),
        controls=[
            ft.SafeArea(
                content=ft.Column(
                    controls=[
                        # Canvas — takes most vertical space
                        ft.Container(content=canvas_stack, expand=True, bgcolor="#080B11"),
                        # Category Bar
                        category_bar,
                        # Adjustment Cards (horizontal scroll)
                        ft.Container(
                            content=adj_cards_row_ctrl,
                            bgcolor="#111521",
                            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                        ),
                        # Single Slider
                        slider_row,
                    ],
                    expand=True,
                    spacing=0,
                ),
                expand=True,
            )
        ],
    )
