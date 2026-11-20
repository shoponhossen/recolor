import flet as ft
import numpy as np
import cv2
import datetime
from pathlib import Path
from utils import get_projects_dir
from .constants import get_mask_icon


def show_alert(page: ft.Page, title: str, msg: str):
    dlg = ft.AlertDialog(
        title=ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        content=ft.Text(msg, size=12, color=ft.Colors.WHITE_70),
        actions=[
            ft.Button(content="OK", on_click=lambda ev: page.pop_dialog()),
        ],
        bgcolor="#151A27",
    )
    page.show_dialog(dlg)


def on_export_mask_image(page: ft.Page, project, li: int, save_buf):
    page.pop_dialog()
    save_buf()

    layer = project.layers[li]
    eff_mask = layer.mask.compute_effective(project.image_array.shape[:2])
    bw = (np.clip(eff_mask, 0.0, 1.0) * 255.0).astype(np.uint8)

    export_dir = get_projects_dir(page).parent / "exports" / "masks"
    export_dir.mkdir(parents=True, exist_ok=True)
    safe_name = (
        "".join(c for c in layer.name if c.isalnum() or c in (" ", "_", "-")).strip()
        or "mask"
    )
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = export_dir / f"{safe_name}_{ts}.png"

    try:
        cv2.imwrite(str(export_path), bw)
        show_alert(
            page,
            "Mask Exported",
            f"Successfully exported black & white mask image to:\n{export_path}",
        )
    except Exception as ex:
        show_alert(page, "Export Failed", f"Could not save mask: {ex}")


async def on_import_mask_image(
    page: ft.Page,
    app,
    project,
    state: dict,
    im_buf: np.ndarray,
    fast_im_buf: np.ndarray,
    prev_w: int,
    prev_h: int,
    fast_w: int,
    fast_h: int,
    refresh_canvas,
    rebuild_mask_list,
    li: int,
):
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
            show_alert(page, "Import Failed", f"Could not load image file:\n{import_path}")
            return

        ih, iw = imp_img.shape[:2]
        oh, ow = project.image_array.shape[:2]

        imp_ratio = iw / float(ih)
        our_ratio = ow / float(oh)

        if abs(imp_ratio - our_ratio) / our_ratio > 0.05:
            show_alert(
                page,
                "Aspect Ratio Mismatch",
                f"Selected image ratio is {iw}x{ih} ({imp_ratio:.2f}:1), "
                f"but project image ratio is {ow}x{oh} ({our_ratio:.2f}:1).\n"
                "Aspect ratio must match the project image.",
            )
            return

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

        if state["main_idx"] == li and state["sub_idx"] == -1:
            np.copyto(
                im_buf,
                cv2.resize(full_mask, (prev_w, prev_h), interpolation=cv2.INTER_LINEAR),
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
            page, "Import Succeeded", f"Replaced mask with '{Path(import_path).name}'."
        )
    except Exception as ex:
        show_alert(page, "Import Error", f"An error occurred: {ex}")


def on_rename_layer(page: ft.Page, project, li: int, appbar_title: ft.Text, rebuild_mask_list):
    page.pop_dialog()
    layer = project.layers[li]
    tf = ft.TextField(
        value=layer.name,
        label="Layer Name",
        autofocus=True,
        border=ft.OutlineInputBorder(
            border_radius=ft.BorderRadius.all(10),
            side=ft.BorderSide(1, ft.Colors.WHITE_24),
        ),
    )

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


def show_parent_options(page: ft.Page, project, li: int, handlers: dict):
    handlers["save_buf"]()
    layer = project.layers[li]

    def mk_opt(icon, title, on_click, color=ft.Colors.WHITE):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=17, color=color),
                    ft.Text(title, size=13, color=color, weight=ft.FontWeight.W_500),
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
                lambda ev: handlers["import"](li),
            ),
            mk_opt(
                ft.Icons.FILE_DOWNLOAD,
                "Export as Image",
                lambda ev: handlers["export"](li),
            ),
            ft.Divider(color=ft.Colors.WHITE_12, height=1),
            mk_opt(
                ft.Icons.REMOVE_CIRCLE_OUTLINE,
                "Erase Child",
                lambda ev: (page.pop_dialog(), handlers["add_sub"](li, "erase")),
                ft.Colors.RED_300,
            ),
            mk_opt(
                ft.Icons.ADD_CIRCLE_OUTLINE,
                "Paint Child",
                lambda ev: (page.pop_dialog(), handlers["add_sub"](li, "paint")),
                ft.Colors.GREEN_ACCENT_400,
            ),
            ft.Divider(color=ft.Colors.WHITE_12, height=1),
            mk_opt(
                ft.Icons.INVERT_COLORS,
                "Invert",
                lambda ev: (page.pop_dialog(), handlers["invert"]()),
            ),
            mk_opt(
                ft.Icons.CONTENT_COPY,
                "Duplicate",
                lambda ev: (page.pop_dialog(), handlers["duplicate"](li)),
            ),
            mk_opt(
                ft.Icons.FORMAT_COLOR_FILL,
                "Fill",
                lambda ev: (page.pop_dialog(), handlers["fill"]()),
            ),
            ft.Divider(color=ft.Colors.WHITE_12, height=1),
            mk_opt(
                ft.Icons.EDIT,
                "Rename",
                lambda ev: handlers["rename"](li),
            ),
            mk_opt(
                ft.Icons.VISIBILITY if layer.visible else ft.Icons.VISIBILITY_OFF,
                "Hide Layer" if layer.visible else "Show Layer",
                lambda ev: (page.pop_dialog(), handlers["toggle_vis"](layer)),
            ),
            mk_opt(
                ft.Icons.DELETE_OUTLINE,
                "Delete",
                lambda ev: handlers["delete"](li),
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


def show_child_options(page: ft.Page, project, li: int, si: int, handlers: dict):
    handlers["save_buf"]()
    layer = project.layers[li]
    if si >= len(layer.mask.sub_masks):
        return
    sm = layer.mask.sub_masks[si]

    def move_child(delta: int):
        page.pop_dialog()
        handlers["save_buf"]()
        n_idx = si + delta
        if 0 <= n_idx < len(layer.mask.sub_masks):
            layer.mask.sub_masks[si], layer.mask.sub_masks[n_idx] = (
                layer.mask.sub_masks[n_idx],
                layer.mask.sub_masks[si],
            )
            handlers["switch_to"](li, n_idx)

    def delete_child():
        page.pop_dialog()
        handlers["save_buf"]()
        if 0 <= si < len(layer.mask.sub_masks):
            del layer.mask.sub_masks[si]
        handlers["switch_to"](li, -1)

    sheet = ft.BottomSheet(
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.REMOVE if sm.mode == "erase" else ft.Icons.ADD,
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
                                    color=ft.Colors.WHITE if si > 0 else ft.Colors.WHITE_24,
                                ),
                                ft.Text(
                                    "Move Up",
                                    size=13,
                                    color=ft.Colors.WHITE if si > 0 else ft.Colors.WHITE_24,
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


def render_mask_list_column(
    column: ft.Column,
    project,
    state: dict,
    handlers: dict,
):
    """Rebuild the controls inside the vertical mask-list panel."""
    column.controls.clear()

    # [+] Add new main mask layer button
    column.controls.append(
        ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ADD, size=16, color=ft.Colors.ORANGE_ACCENT_400),
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
            on_click=lambda ev: handlers["add_main"](),
        )
    )

    for li, layer in enumerate(project.layers):
        is_active_layer = li == state["main_idx"]
        is_main_active = is_active_layer and state["sub_idx"] == -1
        mi_icon = get_mask_icon(layer.mask_type)

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
                                on_click=lambda ev, l=li: handlers["show_parent_opts"](l),
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
                                on_click=lambda ev, l=layer: handlers["toggle_vis"](l),
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
            on_tap=lambda ev, l=li: handlers["switch_to"](l, -1),
            on_long_press_start=lambda ev, l=li: handlers["show_parent_opts"](l),
            on_secondary_tap=lambda ev, l=li: handlers["show_parent_opts"](l),
        )
        column.controls.append(parent_gesture)

        # Child Sub-masks
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
                    handlers["save_buf"]()
                    target = s + delta
                    if 0 <= target < len(project.layers[l].mask.sub_masks):
                        subs = project.layers[l].mask.sub_masks
                        subs[s], subs[target] = subs[target], subs[s]
                        handlers["switch_to"](l, target)

                return cb

            sm_card = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(sm_ico, size=11, color=sm_clr),
                        ft.Text(
                            sm.name,
                            size=9,
                            color=ft.Colors.WHITE if is_sm_sel else ft.Colors.WHITE_60,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            expand=True,
                        ),
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
                on_tap=lambda ev, l=li, s=si_idx: handlers["switch_to"](l, s),
                on_long_press_start=lambda ev, l=li, s=si_idx: handlers["show_child_opts"](
                    l, s
                ),
                on_secondary_tap=lambda ev, l=li, s=si_idx: handlers["show_child_opts"](
                    l, s
                ),
            )
            column.controls.append(child_gesture)

    try:
        column.update()
    except Exception:
        pass
