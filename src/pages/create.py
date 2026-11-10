import flet as ft
from pathlib import Path
from app import ReColor
from utils import load_rgba, arr_to_jpeg_bytes
import datetime


def create_view(page: ft.Page, app: ReColor) -> ft.View:
    selected_image_path: str | None = None
    default_sample_path = str(Path(r"D:\Projects\recolor\default.jpg").resolve())

    # Pre-generate a default unique project name
    now_str = datetime.datetime.now().strftime("%b%d_%H%M")
    initial_name = f"Project_{now_str}"

    name_field = ft.TextField(
        value=initial_name,
        label="Project Name",
        max_length=25,
        filled=True,
        bgcolor="#141824",
        border=ft.OutlineInputBorder(
            border_radius=ft.BorderRadius.all(12),
            side=ft.BorderSide(1, ft.Colors.WHITE_24),
        ),
        suffix=".rclr",
    )

    image_preview = ft.Image(
        src=None,
        width=220,
        height=220,
        fit=ft.BoxFit.COVER,
        border_radius=ft.BorderRadius.all(14),
        visible=False,
    )

    status_icon = ft.Icon(ft.Icons.IMAGE_OUTLINED, size=32, color=ft.Colors.WHITE_38)
    status_title = ft.Text("No image selected", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE_70)
    status_subtitle = ft.Text("Pick an image from your device or use sample", size=11, color=ft.Colors.WHITE_38)

    preview_card = ft.Container(
        content=ft.Column(
            controls=[
                image_preview,
                status_icon,
                status_title,
                status_subtitle,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=6,
        ),
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.all(16),
        bgcolor="#121622",
        border_radius=ft.BorderRadius.all(16),
        border=ft.Border.all(1, ft.Colors.WHITE_12),
        height=280,
    )

    create_btn = ft.Button(
        content=ft.Row([
            ft.Text("Start Color Grading", size=15, weight=ft.FontWeight.BOLD),
            ft.Icon(ft.Icons.ARROW_FORWARD, size=18),
        ], alignment=ft.MainAxisAlignment.CENTER),
        bgcolor=ft.Colors.ORANGE_ACCENT_700,
        color=ft.Colors.WHITE,
        disabled=True,
        height=50,
    )

    def set_chosen_image(path: str):
        nonlocal selected_image_path
        selected_image_path = path
        try:
            arr = load_rgba(path)
            h, w = arr.shape[:2]
            image_preview.src = arr_to_jpeg_bytes(arr, quality=75)
            image_preview.visible = True
            status_icon.visible = False
            status_title.value = Path(path).name
            status_title.color = ft.Colors.WHITE
            status_subtitle.value = f"Resolution: {w} × {h} px"
            status_subtitle.color = ft.Colors.GREEN_ACCENT_400
            create_btn.disabled = False
            preview_card.border = ft.Border.all(1.5, ft.Colors.ORANGE_ACCENT_400)
        except Exception as ex:
            status_title.value = "Failed to load image"
            status_title.color = ft.Colors.RED_ACCENT_400
            status_subtitle.value = str(ex)
            create_btn.disabled = True

        try:
            preview_card.update()
            create_btn.update()
        except Exception:
            pass

    async def on_pick_file(e):
        try:
            files = await app.file_picker.pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE,
            )
            if files and len(files) > 0:
                set_chosen_image(files[0].path)
        except Exception as ex:
            print("File picker error:", ex)

    def on_use_sample(e):
        if Path(default_sample_path).exists():
            set_chosen_image(default_sample_path)
        else:
            status_title.value = "Sample portrait not found"
            status_title.color = ft.Colors.RED_ACCENT_400
            try:
                preview_card.update()
            except Exception:
                pass

    async def on_create_project(e):
        proj_name = name_field.value.strip() or initial_name
        if not selected_image_path:
            return

        app.projects_manager.create_project(proj_name, selected_image_path)
        await page.push_route("/editor")

    create_btn.on_click = on_create_project

    async def go_back(e):
        await page.push_route("/")

    return ft.View(
        route="/create",
        bgcolor="#0B0F17",
        appbar=ft.AppBar(
            bgcolor="#111521",
            leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=go_back),
            title=ft.Text("New Project", size=18, weight=ft.FontWeight.BOLD),
        ),
        controls=[
            ft.SafeArea(
                content=ft.Container(
                    padding=ft.Padding.symmetric(horizontal=20, vertical=16),
                    content=ft.Column(
                        controls=[
                            ft.Text("Project Name", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE_70),
                            name_field,
                            ft.Container(height=6),
                            ft.Text("Image Source", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE_70),
                            ft.Row(
                                controls=[
                                    ft.Button(
                                        content=ft.Row([
                                            ft.Icon(ft.Icons.PHOTO_LIBRARY, size=18, color=ft.Colors.ORANGE_ACCENT_400),
                                            ft.Text("Choose Photo", size=12),
                                        ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
                                        bgcolor="#182032",
                                        color=ft.Colors.WHITE,
                                        on_click=on_pick_file,
                                        expand=True,
                                        height=46,
                                    ),
                                    ft.Button(
                                        content=ft.Row([
                                            ft.Icon(ft.Icons.AUTO_AWESOME, size=18, color=ft.Colors.ORANGE_ACCENT_400),
                                            ft.Text("Sample Portrait", size=12),
                                        ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
                                        bgcolor="#182032",
                                        color=ft.Colors.WHITE,
                                        on_click=on_use_sample,
                                        expand=True,
                                        height=46,
                                    ),
                                ],
                                spacing=10,
                            ),
                            ft.Container(height=6),
                            preview_card,
                            ft.Container(expand=True),
                            create_btn,
                        ],
                        expand=True,
                        spacing=8,
                    ),
                ),
                expand=True,
            )
        ],
    )
