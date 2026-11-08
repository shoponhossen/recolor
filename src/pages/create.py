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
        border_radius=ft.BorderRadius.all(10),
        focused_border_color=ft.Colors.ORANGE_ACCENT_400,
        suffix=".rclr",
    )

    image_preview = ft.Image(
        src=None,
        width=200,
        height=200,
        fit=ft.BoxFit.COVER,
        border_radius=ft.BorderRadius.all(12),
        visible=False,
    )

    status_text = ft.Text(
        "No image selected yet",
        size=12,
        color=ft.Colors.WHITE_54,
    )

    create_btn = ft.Button(
        content="Start Color Grading",
        icon=ft.Icons.ARROW_FORWARD,
        bgcolor=ft.Colors.ORANGE_ACCENT_700,
        color=ft.Colors.WHITE,
        disabled=True,
        height=48,
    )

    def set_chosen_image(path: str):
        nonlocal selected_image_path
        selected_image_path = path
        try:
            arr = load_rgba(path)
            # Small preview
            image_preview.src = arr_to_jpeg_bytes(arr, quality=70)
            image_preview.visible = True
            status_text.value = f"Selected: {Path(path).name} ({arr.shape[1]}x{arr.shape[0]})"
            status_text.color = ft.Colors.GREEN_ACCENT_400
            create_btn.disabled = False
        except Exception as ex:
            status_text.value = f"Failed to load image: {ex}"
            status_text.color = ft.Colors.RED_ACCENT_400
            create_btn.disabled = True

        try:
            image_preview.update()
            status_text.update()
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
            status_text.value = "Sample default.jpg not found."
            status_text.color = ft.Colors.RED_ACCENT_400
            try:
                status_text.update()
            except Exception:
                pass

    async def on_create_project(e):
        proj_name = name_field.value.strip() or initial_name
        if not selected_image_path:
            return

        # Create project in manager
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
                    padding=ft.Padding.all(20),
                    content=ft.Column(
                        controls=[
                            ft.Text("Project Details", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            name_field,
                            ft.Container(height=10),
                            ft.Text("Choose Image Source", size=14, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE_70),
                            ft.Row(
                                controls=[
                                    ft.OutlinedButton(
                                        "Select from Device",
                                        icon=ft.Icons.PHOTO_LIBRARY,
                                        on_click=on_pick_file,
                                        expand=True,
                                        height=44,
                                    ),
                                    ft.OutlinedButton(
                                        "Sample Portrait",
                                        icon=ft.Icons.AUTO_AWESOME,
                                        on_click=on_use_sample,
                                        expand=True,
                                        height=44,
                                    ),
                                ],
                                spacing=10,
                            ),
                            ft.Container(height=10),
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        image_preview,
                                        status_text,
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                alignment=ft.Alignment.CENTER,
                                padding=ft.Padding.symmetric(vertical=15),
                            ),
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
