import flet as ft
from app import ReColor, ProjectManager, Project
from utils import arr_to_bytes
from components.slider import CenterSlider
from backend.backend import Exposure


def editor_view(page: ft.Page, app: ReColor) -> ft.View:
    ### Cleanup
    page.overlay.clear()

    # Dev Only
    pm: ProjectManager = app.projects_manager
    # pm.load_project("Untitled")
    if pm.project is None:
        pm.create_project("Default", r"D:\Projects\recolor\default.jpg")

    exp = Exposure()

    ### Handlers
    async def open_selector_page(e):
        pm.project.save()
        await page.push_route("/editor/selector")

    img = ft.RawImage(
        fit=ft.BoxFit.CONTAIN,
        width=float("inf"),
        height=float("inf"),
    )

    selected_mask_container = ft.Container(
        ft.Dropdown(
            width=150,
            value="global",
            # border_radius=ft.BorderRadius.all(8),
            options=[
                ft.DropdownOption(key="global", text="Global"),
                ft.DropdownOption(key="bob", text="Bob"),
            ],
        ),
        bottom=10,
        right=10,
        blur=5,
        bgcolor=ft.Colors.with_opacity(0.5, "#ffffff"),
        border_radius=ft.BorderRadius.all(8),
    )

    canvas = ft.Stack(
        expand=True,
        controls=[
            ft.Container(
                content=img,
                border=ft.Border.all(1),
                left=0,
                top=0,
                right=0,
                bottom=0,
            ),
            selected_mask_container,
        ],
    )

    page.run_task(img.render, pm.project.image_array)

    async def on_slider_start(e):
        selected_mask_container.visible = False
        print("Start.")

    async def on_slider_end(e):
        selected_mask_container.visible = True
        await img.render(pm.project.image_array)
        print("End.")

    def on_slider_change(e):
        print("Hello World")
        value = e.control.value
        pm.project.selected_layer.values[exp] = value

        pm.project.render_preview()

    slider = CenterSlider(
        min=-100,
        max=100,
        on_change_start=on_slider_start,
        on_change_end=on_slider_end,
        on_change=on_slider_change,
    )

    cards = ft.Container(
        height=75,
        content=ft.Row(
            [ft.Card(width=75, height=75) for _ in range(10)],
            scroll=ft.ScrollMode.ALWAYS,
        ),
    )

    main_area = ft.Column([canvas, slider, cards], expand=True, spacing=5)

    return ft.View(
        route="/editor",
        appbar=ft.AppBar(
            title=ft.Text(f"{pm.project.name} Editor"),
            actions=[
                ft.IconButton(ft.Icons.ACCOUNT_BOX, on_click=open_selector_page),
                ft.IconButton(ft.Icons.SAVE, on_click=lambda e: pm.project.save()),
            ],
        ),
        controls=[ft.SafeArea(content=main_area, expand=True)],
    )
